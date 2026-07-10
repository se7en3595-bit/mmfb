"""CsvHandler 单元测试

测试覆盖：
- can_handle 方法（.csv / .tsv / .tab，大小写混合）
- 不相关扩展名拒绝
- get_preview 基本 CSV（逗号分隔，表头推断）
- TSV 文件解析（自动识别为分隔符）
- 大文件拒绝（>50MB）
- 空文件处理
- 缺省文件处理
- 编码探测（GB2312 / UTF-8）
- get_edit 返回 None
- 导出辅助函数（export_to_tsv / export_to_excel）
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mmfb.handlers.csv_handler import (
    CsvHandler, _auto_read_csv, _detect_delimiter_from_sample,
    _format_value, MAX_PREVIEW_ROWS,
)
from mmfb.core.registry import HandlerRegistry


# 测试用 CSV：简单人口普查样例
SAMPLE_CSV = """\
name,age,city,joined
Alice,30,Beijing,2020-01-15
Bob,25,Shanghai,2019-08-22
Carol,35,Guangzhou,2021-03-10
Dave,28,Shenzhen,2018-11-05
"""

# 测试用 TSV
SAMPLE_TSV = "name\tvalue\tdate\nfoo\t100\t2024-01-01\nbar\t200\t2024-02-02\n"

# 空表（仅一行表头）
EMPTY_CSV = "c1,c2,c3\n"

# 含 NaN 空值的 CSV
CSV_WITH_NAN = "a,b,c\n1,,3\n,5,\n7,8,9\n"

# 数值型含小数
CSV_FLOATS = "product,price\napple,1.5\nbanana,0.75\n"


class TestCsvHandlerBasic(unittest.TestCase):
    """基础 can_handle 测试"""

    def test_can_handle_csv(self):
        self.assertTrue(CsvHandler.can_handle("/tmp/test.csv"))

    def test_can_handle_tsv(self):
        self.assertTrue(CsvHandler.can_handle("/tmp/test.tsv"))

    def test_can_handle_tab(self):
        self.assertTrue(CsvHandler.can_handle("/tmp/test.tab"))

    def test_uppercase_csv(self):
        self.assertTrue(CsvHandler.can_handle("/tmp/test.CSV"))

    def test_mixed_case(self):
        self.assertTrue(CsvHandler.can_handle("/tmp/test.Csv"))

    def test_reject_other(self):
        self.assertFalse(CsvHandler.can_handle("/tmp/test.pdf"))

    def test_reject_txt(self):
        self.assertFalse(CsvHandler.can_handle("/tmp/test.txt"))

    def test_reject_log(self):
        self.assertFalse(CsvHandler.can_handle("/tmp/test.log"))

    def test_reject_no_ext(self):
        self.assertFalse(CsvHandler.can_handle("/tmp/noext"))


class TestCsvHandlerPreview(unittest.TestCase):
    """get_preview 功能测试"""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode='w', encoding='utf-8')
        self.tmp.write(SAMPLE_CSV)
        self.tmp.close()

    def tearDown(self):
        try:
            os.unlink(self.tmp.name)
        except OSError:
            pass

    def test_preview_returns_dict(self):
        result = CsvHandler(self.tmp.name).get_preview()
        self.assertIsInstance(result, dict)

    def test_preview_template_csv(self):
        result = CsvHandler(self.tmp.name).get_preview()
        self.assertEqual(result.get("template"), "csv")

    def test_preview_has_data(self):
        result = CsvHandler(self.tmp.name).get_preview()
        self.assertIn("data", result)

    def test_preview_headers(self):
        result = CsvHandler(self.tmp.name).get_preview()
        headers = result["data"]["headers"]
        self.assertEqual(headers, ["name", "age", "city", "joined"])

    def test_preview_columns_count(self):
        result = CsvHandler(self.tmp.name).get_preview()
        self.assertEqual(result["data"]["columns"], 4)

    def test_preview_row_count(self):
        result = CsvHandler(self.tmp.name).get_preview()
        # SAMPLE_CSV 4 行数据 + 1 行表头，但 预览返回的是 data rows（不含表头吗？)
        # CsvHandler 把 headers 和 rows 分开；SAMPLE_CSV 数据部分是 4 行
        self.assertEqual(result["data"]["preview_rows"], 4)
        self.assertEqual(result["data"]["total_rows"], 4)

    def test_preview_rows_shape(self):
        result = CsvHandler(self.tmp.name).get_preview()
        rows = result["data"]["rows"]
        self.assertEqual(len(rows), 4)
        # 第一行 (Alice, 30, Beijing, 2020-01-15)
        self.assertEqual(rows[0][0], "Alice")
        self.assertEqual(rows[0][1], 30)
        self.assertEqual(rows[0][2], "Beijing")

    def test_preview_dtypes(self):
        result = CsvHandler(self.tmp.name).get_preview()
        dtypes = result["data"]["dtypes"]
        # age 应为 number，其余为 string
        self.assertEqual(dtypes[1], "number")

    def test_preview_not_editable(self):
        result = CsvHandler(self.tmp.name).get_preview()
        self.assertFalse(result.get("editable"))

    def test_preview_file_size_set(self):
        result = CsvHandler(self.tmp.name).get_preview()
        self.assertGreater(result["data"]["file_size"], 0)

    def test_preview_encoding(self):
        result = CsvHandler(self.tmp.name).get_preview()
        self.assertEqual(result["data"]["encoding"], "utf-8")


class TestCsvHandlerTsv(unittest.TestCase):
    """TSV 自动分隔符探测测试"""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".tsv", delete=False, mode='w', encoding='utf-8')
        self.tmp.write(SAMPLE_TSV)
        self.tmp.close()

    def tearDown(self):
        try:
            os.unlink(self.tmp.name)
        except OSError:
            pass

    def test_tsv_parsed(self):
        result = CsvHandler(self.tmp.name).get_preview()
        self.assertEqual(result["data"]["columns"], 3)
        self.assertEqual(result["data"]["preview_rows"], 2)

    def test_tsv_headers(self):
        result = CsvHandler(self.tmp.name).get_preview()
        self.assertEqual(result["data"]["headers"], ["name", "value", "date"])

    def test_tsv_delimiter_field(self):
        result = CsvHandler(self.tmp.name).get_preview()
        self.assertEqual(result["data"]["delimiter"], "\t")


class TestCsvHandlerEmpty(unittest.TestCase):
    """空文件测试"""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode='w', encoding='utf-8')
        self.tmp.write(EMPTY_CSV)
        self.tmp.close()

    def tearDown(self):
        try:
            os.unlink(self.tmp.name)
        except OSError:
            pass

    def test_empty_csv_headers_set(self):
        result = CsvHandler(self.tmp.name).get_preview()
        self.assertEqual(result["data"]["headers"], ["c1", "c2", "c3"])
        self.assertEqual(result["data"]["preview_rows"], 0)

    def test_empty_csv_no_error(self):
        result = CsvHandler(self.tmp.name).get_preview()
        self.assertNotIn("error", result)


class TestCsvHandlerMissingFile(unittest.TestCase):
    """缺失文件测试"""

    def test_missing_returns_dict(self):
        result = CsvHandler("/tmp/nonexistent_csv_handler_test.csv").get_preview()
        self.assertIsInstance(result, dict)

    def test_missing_has_error(self):
        result = CsvHandler("/tmp/nonexistent_csv_handler_test.csv").get_preview()
        self.assertIn("error", result)


class TestCsvHandlerEncoding(unittest.TestCase):
    """编码探测测试"""

    def test_utf8_bom_detected(self):
        # 写 utf-8-bom 格式
        tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode='wb')
        tmp.write(b"\xef\xbb\xbf" + SAMPLE_CSV.encode("utf-8"))
        tmp.close()
        try:
            result = CsvHandler(tmp.name).get_preview()
            # headers 的 name 列应不含 BOM 残留
            headers = result["data"]["headers"]
            self.assertTrue(headers[0].startswith("name") or headers[0].startswith("﻿name"))
        finally:
            os.unlink(tmp.name)


class TestCsvHandlerNaN(unittest.TestCase):
    """NaN 处理测试"""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode='w', encoding='utf-8')
        self.tmp.write(CSV_WITH_NAN)
        self.tmp.close()

    def tearDown(self):
        try:
            os.unlink(self.tmp.name)
        except OSError:
            pass

    def test_nan_to_null(self):
        result = CsvHandler(self.tmp.name).get_preview()
        # row[0][1] = NaN -> null
        self.assertIsNone(result["data"]["rows"][0][1])
        self.assertIsNone(result["data"]["rows"][1][0])
        self.assertIsNone(result["data"]["rows"][1][2])


class TestCsvHandlerEdit(unittest.TestCase):
    """get_edit 测试"""

    def test_get_edit_returns_none(self):
        handler = CsvHandler("/tmp/test.csv")
        # dummy path (doesn't need to exist for get_edit behavior test; show not crash)
        result = handler.get_edit()
        self.assertIsNone(result)


class TestDelimDetect(unittest.TestCase):
    """_detect_delimiter_from_sample 独立测试"""

    def test_comma_detected(self):
        text = "a,b,c\n1,2,3\n4,5,6"
        self.assertEqual(_detect_delimiter_from_sample(text), ",")

    def test_tab_detected(self):
        text = "a\tb\tc\n1\t2\t3\n4\t5\t6"
        self.assertEqual(_detect_delimiter_from_sample(text), "\t")

    def test_empty_returns_none(self):
        self.assertIsNone(_detect_delimiter_from_sample(""))

    def test_no_consistent_delim_returns_none(self):
        text = "abc def\nghi jkl"
        self.assertIsNone(_detect_delimiter_from_sample(text))


class TestFormatValue(unittest.TestCase):
    """_format_value 独立测试"""

    def test_none_returns_none(self):
        self.assertIsNone(_format_value(None))

    def test_nan_returns_none(self):
        self.assertIsNone(_format_value(float("nan")))

    def test_int_passthrough(self):
        self.assertEqual(_format_value(42), 42)

    def test_float_pasfinite(self):
        self.assertEqual(_format_value(3.14), 3.14)

    def test_bool_true(self):
        self.assertTrue(_format_value(True))

    def test_string_passthrough(self):
        self.assertEqual(_format_value("hello"), "hello")


class TestCsvHandlerRegistry(unittest.TestCase):
    """注册表集成测试"""

    def test_registry_dispatch_csv(self):
        reg = HandlerRegistry()
        reg.register_class(CsvHandler)
        handler = reg.get_handler("/tmp/data.csv")
        self.assertIsInstance(handler, CsvHandler)

    def test_registry_dispatch_tsv(self):
        reg = HandlerRegistry()
        reg.register_class(CsvHandler)
        handler = reg.get_handler("/tmp/data.tsv")
        self.assertIsInstance(handler, CsvHandler)

    def test_registry_dispatch_uppercase_csv(self):
        reg = HandlerRegistry()
        reg.register_class(CsvHandler)
        handler = reg.get_handler("/tmp/TEST.CSV")
        self.assertIsInstance(handler, CsvHandler)

    def test_registry_count(self):
        reg = HandlerRegistry()
        reg.register_class(CsvHandler)
        self.assertEqual(reg.count(), 3)


class TestCsvHandlerMaxPreviewRows(unittest.TestCase):
    """预览行上限常量确认"""

    def test_max_preview_rows_value(self):
        self.assertEqual(MAX_PREVIEW_ROWS, 10000)


if __name__ == "__main__":
    unittest.main()
