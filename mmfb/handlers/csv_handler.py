"""CSV/TSV/Tab 表格格式处理器

职责：
1. 使用 pandas 读取 .csv / .tsv / .tab 文件，自动探测分隔符与编码
2. 返回结构化表格数据（headers + rows + dtypes + shape）
3. 支持大文件自动截断预览（>50MB 拒绝，>10000 行截断）
4. 提供类型推断元数据，供前端高亮/排序/分页使用
5. 不提供就地编辑（表格体量远大于 textarea 承载能力）；导出通过 Bridge 后端执行

安全：
- 单文件上限 50MB（与 file_handler.MAX_FILE_SIZE_BYTES 同步）
- 类型强制转为 JSON 兼容（datetime → 字符串、NaN → null）
"""
import json
import os
from typing import Any, Dict, List, Optional

import pandas as pd

from mmfb.core.handler_base import BaseHandler
from mmfb.core.file_handler import MAX_FILE_SIZE_BYTES


# 表格扩展名（.log 由 TextHandler 专属处理）
CSV_EXTENSIONS: List[str] = [".csv", ".tsv", ".tab"]

# 预览行上限（超过后截断并标记 truncated=True）
MAX_PREVIEW_ROWS = 10000

# 单元格字节上限（单单元格超过时截断，防止 JSON 爆炸）
MAX_CELL_BYTES = 4096


def _is_na(value: Any) -> bool:
    """判断 pandas 缺失值（NaN / NaT / None）"""
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (ValueError, TypeError):
        return False


def _format_value(value: Any) -> Any:
    """将单个单元格值转为 JSON 兼容类型

    - int/float/bool → 原生
    - NaN/NaT/None → None
    - datetime/Timestamp/Period → ISO 字符串
    - 其他 → str，并截断超长内容
    """
    if _is_na(value):
        return None
    if isinstance(value, bool):
        return bool(value)
    if isinstance(value, int) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, float):
        if value != value or value == float("inf") or value == float("-inf"):
            return None
        return float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    # 其他（Period、timedelta、Categorical、普通对象）
    s = str(value)
    if len(s.encode("utf-8")) > MAX_CELL_BYTES:
        s = s[:1366] + "...(truncated)"
    return s


def _detect_delimiter_from_sample(sample_text: str) -> Optional[str]:
    """从采样文本猜测分隔符

    仅适用：逗号、制表符、分号、竖线。
    返回 None 时由 pandas 回退到 engine='python'。
    """
    if not sample_text:
        return None
    # 只看前几行
    lines = sample_text.splitlines()[:5]
    if not lines:
        return None

    candidates = [
        (",", "comma"),
        ("\t", "tab"),
        (";", "semicolon"),
        ("|", "pipe"),
    ]

    best_delim = None
    best_score = 0

    for delim, _ in candidates:
        counts = [line.count(delim) for line in lines]
        # 所有行都包含至少一个且数量一致时最可信
        if all(c > 0 for c in counts):
            avg = sum(counts) / len(counts)
            # 一致性加分
            if len(set(counts)) == 1:
                avg *= 1.5
            if avg > best_score:
                best_score = avg
                best_delim = delim

    return best_delim


def _auto_read_csv(path: str, encoding: str) -> pd.DataFrame:
    """自动读 CSV，先探测分隔符，再构造 DataFrame

    策略：
    1. 读前 8KB 作为样本
    2. 探测分隔符
    3. 首次尝试 engine='c'（快）
    4. 失败则 engine='python' + sep=None 兜底
    """
    # 读样本探测分隔符（在 50MB 内才能 mmap，先 binary 读前 8KB）
    sample_bytes = min(8192, os.path.getsize(path) if os.path.isfile(path) else 0)
    try:
        with open(path, "rb") as f:
            sample_raw = f.read(sample_bytes)
        sample_text = sample_raw.decode(encoding, errors="replace")
    except OSError:
        sample_text = ""

    delimiter = _detect_delimiter_from_sample(sample_text)

    # pandas 读取尝试
    read_kwargs: Dict[str, Any] = {
        "encoding": encoding,
        "on_bad_lines": "warn",
        "low_memory": False,
    }
    if delimiter is not None:
        read_kwargs["sep"] = delimiter
        read_kwargs["engine"] = "c"
    else:
        read_kwargs["sep"] = None
        read_kwargs["engine"] = "python"

    try:
        df = pd.read_csv(path, **read_kwargs)
    except Exception:
        # 最后的兜底：engine=python + sep=None（最宽容）
        try:
            df = pd.read_csv(path, sep=None, engine="python", encoding=encoding, on_bad_lines="skip")
        except Exception:
            raise

    return df


class CsvHandler(BaseHandler):
    """CSV/TSV/Tab 表格处理器

    支持的扩展名：
        .csv, .tsv, .tab

    特性：
        - pandas 自动类型推断
        - 编码 UTF-8 / GB18030 / chardet 探测
        - 分隔符自动识别（逗号、制表符、分号、竖线）
        - 预览行数上限 10000；超过时截断并标记 truncated
        - 单单元格 4KB 截断，防止 JSON 爆炸
    """

    extensions = CSV_EXTENSIONS

    @classmethod
    def detect_encoding(cls, raw: bytes) -> str:
        """探测文件编码（复用 TextHandler 策略）

        1. UTF-8 优先
        2. chardet 备用
        3. GB18030 中文兜底
        """
        try:
            raw.decode("utf-8")
            return "utf-8"
        except UnicodeDecodeError:
            pass

        try:
            import chardet
            if len(raw) >= 256:
                result = chardet.detect(raw[:65536])
                enc = result.get("encoding")
                confidence = result.get("confidence", 0)
                if enc and confidence > 0.5:
                    return enc.lower()
        except Exception:
            pass

        try:
            raw.decode("gb18030")
            return "gb18030"
        except UnicodeDecodeError:
            pass

        return "utf-8"

    def get_preview(self) -> Optional[Dict[str, Any]]:
        """获取表格预览数据

        返回字典：
        - mime: text/csv（或 text/tab-separated-values 根据扩展名）
        - template: 'csv'
        - data.headers: 列名列表
        - data.columns: 列数
        - data.total_rows: 文件总行数（未截断时等于 len(rows)）
        - data.preview_rows: 实际返回的行数
        - data.rows: 二维数组，单元格已是 JSON 兼容类型
        - data.dtypes: 每列推断类型字符串
        - data.file_path: 原文件绝对路径
        - data.file_size: 文件字节数
        - data.encoding: 探测到的编码
        - data.delimiter 探测到的分隔符（用于显示）
        - data.truncated: bool，是否截断
        - editable: False（表格编辑由专属工具完成）
        """
        try:
            if not os.path.isfile(self.path):
                return self._error_result("file not found")

            file_size = os.path.getsize(self.path)
            if file_size == 0:
                return self._empty_result(file_size, "empty file")

            if file_size > MAX_FILE_SIZE_BYTES:
                return self._error_result(
                    f"file too large: {file_size} bytes (max {MAX_FILE_SIZE_BYTES})"
                )

            # 编码探测（读取最多 65536 字节样本）
            try:
                with open(self.path, "rb") as f:
                    raw_sample = f.read(min(65536, file_size))
                encoding = self.detect_encoding(raw_sample)
                sample_text = raw_sample.decode(encoding, errors="replace")
            except OSError:
                encoding = "utf-8"
                sample_text = ""

            # 探测分隔符（前 3 行校验）
            sample_lines = sample_text.splitlines()[:3]
            if len(sample_lines) > 0:
                # 检查是否包含常见分隔符
                has_delim = any(line.count(",") > 0 or line.count("\t") > 0 or line.count(";") > 0 or line.count("|") > 0 for line in sample_lines)
                if not has_delim:
                    return None  # 看起来不像 CSV，回退到 TextHandler

            # pandas 读取
            try:
                df = _auto_read_csv(self.path, encoding)
            except Exception as e:
                return self._error_result(f"parse error: {e}")

            total_rows = len(df)
            columns = len(df.columns)

            # 截断判断
            truncated = total_rows > MAX_PREVIEW_ROWS
            if truncated:
                df_preview = df.head(MAX_PREVIEW_ROWS)
            else:
                df_preview = df

            # 列名
            headers = [str(c) for c in df.columns.tolist()]

            # 类型字符串（前端用于样式/排序策略）
            dtype_map = {
                "int64": "number",
                "int32": "number",
                "float64": "number",
                "float32": "number",
                "bool": "boolean",
                "datetime64[ns]": "datetime",
                "object": "string",
            }
            dtypes = [dtype_map.get(str(dt), "string") for dt in df.dtypes]

            # 转二维数组（行优先，每行是 list）
            # 优先用 itertuples（快），再逐单元格格式化
            rows: List[List[Any]] = []
            for _, row in df_preview.iterrows():
                formatted_row = [_format_value(v) for v in row.tolist()]
                rows.append(formatted_row)

            # 分隔符显示：从文件扩展名推断最可能的一个
            delim_display = "\t" if self.path.lower().endswith((".tsv", ".tab")) else ","

            return {
                "mime": self.get_mime(),
                "template": "csv",
                "data": {
                    "headers": headers,
                    "rows": rows,
                    "columns": columns,
                    "total_rows": total_rows,
                    "preview_rows": len(rows),
                    "dtypes": dtypes,
                    "file_path": self.path,
                    "file_size": file_size,
                    "encoding": encoding,
                    "delimiter": delim_display,
                    "truncated": truncated,
                },
                "editable": False,
            }
        except Exception as e:
            return self._error_result(str(e))

    def get_edit(self) -> Optional[Dict[str, Any]]:
        """CSV 表格 v1 不开放直接在应用内编辑

        预留接口，未来可支持 cell-level 编辑并调用 save_csv_cells。
        """
        return None

    def _error_result(self, error_msg: str) -> Dict[str, Any]:
        return {
            "mime": "text/csv",
            "template": "csv",
            "data": {
                "headers": [],
                "rows": [],
                "columns": 0,
                "total_rows": 0,
                "preview_rows": 0,
                "dtypes": [],
                "file_path": self.path,
                "file_size": 0,
                "encoding": "utf-8",
                "delimiter": ",",
                "truncated": False,
            },
            "editable": False,
            "error": error_msg,
        }

    def _empty_result(self, file_size: int, error_msg: str) -> Dict[str, Any]:
        return {
            "mime": "text/csv",
            "template": "csv",
            "data": {
                "headers": [],
                "rows": [],
                "columns": 0,
                "total_rows": 0,
                "preview_rows": 0,
                "dtypes": [],
                "file_path": self.path,
                "file_size": file_size,
                "encoding": "utf-8",
                "delimiter": ",",
                "truncated": False,
            },
            "editable": False,
            "error": error_msg,
        }


# ========== 导出辅助（被 Bridge 调用） ==========

def export_to_excel(src_path: str, dst_path: str) -> Dict[str, Any]:
    """将 CSV/TSV 导出为 .xlsx

    返回: {"ok": true, "path": dst} 或 {"ok": false, "error": "..."}
    """
    try:
        import openpyxl
        enc = CsvHandler.detect_encoding(open(src_path, "rb").read(min(65536, os.path.getsize(src_path))))
        df = _auto_read_csv(src_path, enc)
        df.to_excel(dst_path, index=False, engine="openpyxl")
        return {"ok": True, "path": dst_path}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def export_to_tsv(src_path: str, dst_path: str) -> Dict[str, Any]:
    """将 CSV/TSV 标准化导出为 .tsv（UTF-8-BOM + 制表符）"""
    try:
        enc = CsvHandler.detect_encoding(open(src_path, "rb").read(min(65536, os.path.getsize(src_path))))
        df = _auto_read_csv(src_path, enc)
        # utf-8-sig 让 Excel 能正确识别
        df.to_csv(dst_path, sep="\t", index=False, encoding="utf-8-sig")
        return {"ok": True, "path": dst_path}
    except Exception as e:
        return {"ok": False, "error": str(e)}
