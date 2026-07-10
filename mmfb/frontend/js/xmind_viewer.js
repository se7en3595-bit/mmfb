/**
 * XMind 思维导图查看器
 * 支持多画布切换、树形主题展开/折叠
 */

class MMFBXmindViewer {
    constructor(container) {
        this.container = container;
        this.sheets = [];
        this.currentSheet = null;
        this.expandedNodes = new Set();
    }

    /**
     * 渲染 XMind 内容
     * @param {Object} data - read_content() 返回的数据
     */
    render(data) {
        this.sheets = data.sheets || [];
        this.container.innerHTML = "";

        if (this.sheets.length === 0) {
            this.container.innerHTML = `<div class="xmind-empty">未找到画布</div>`;
            return;
        }

        // 创建布局
        this.container.classList.add("xmind-viewer");

        // 画布切换工具栏
        const toolbar = document.createElement("div");
        toolbar.className = "xmind-toolbar";
        toolbar.innerHTML = `
            <div class="xmind-toolbar-left">
                <span class="xmind-sheet-label">画布：</span>
                <select id="xmind-sheet-select" class="xmind-sheet-select"></select>
            </div>
            <div class="xmind-toolbar-right">
                <button id="xmind-expand-all" class="xmind-btn">全部展开</button>
                <button id="xmind-collapse-all" class="xmind-btn">全部折叠</button>
            </div>
        `;
        this.container.appendChild(toolbar);

        // 填充画布选项
        const select = toolbar.querySelector("#xmind-sheet-select");
        this.sheets.forEach((sheet, index) => {
            const option = document.createElement("option");
            option.value = sheet.id;
            option.textContent = sheet.name;
            if (index === 0) option.selected = true;
            select.appendChild(option);
        });

        // 创建树形内容区
        const treeContainer = document.createElement("div");
        treeContainer.className = "xmind-tree-container";
        treeContainer.id = "xmind-tree-root";
        this.container.appendChild(treeContainer);

        // 绑定事件
        select.addEventListener("change", (e) => this._switchSheet(e.target.value));
        toolbar.querySelector("#xmind-expand-all").addEventListener("click", () => this._expandAll());
        toolbar.querySelector("#xmind-collapse-all").addEventListener("click", () => this._collapseAll());

        // 默认显示第一个画布
        this._switchSheet(this.sheets[0].id);
    }

    /**
     * 切换画布
     */
    _switchSheet(sheetId) {
        this.currentSheet = this.sheets.find(s => s.id === sheetId);
        if (!this.currentSheet) return;

        const root = this.container.querySelector("#xmind-tree-root");
        root.innerHTML = "";
        this.expandedNodes.clear();

        if (this.currentSheet.rootTopic && this.currentSheet.rootTopic.title) {
            this._renderTopic(this.currentSheet.rootTopic, root, 0);
        } else {
            root.innerHTML = `<div class="xmind-empty">画布为空</div>`;
        }
    }

    /**
     * 递归渲染主题树
     */
    _renderTopic(topic, parentElement, depth) {
        const topicEl = document.createElement("div");
        topicEl.className = "xmind-topic";
        topicEl.dataset.topicId = topic.id;
        topicEl.style.paddingLeft = `${depth * 20}px`;

        // 检查是否有子主题
        const hasChildren = topic.children && topic.children.length > 0;
        const isExpanded = this.expandedNodes.has(topic.id);

        // 构建标题行
        const header = document.createElement("div");
        header.className = "xmind-topic-header";

        // 展开/折叠按钮
        if (hasChildren) {
            const toggle = document.createElement("span");
            toggle.className = `xmind-toggle ${isExpanded ? "expanded" : ""}`;
            toggle.textContent = isExpanded ? "▼" : "▶";
            toggle.addEventListener("click", (e) => {
                e.stopPropagation();
                this._toggleNode(topic.id);
            });
            header.appendChild(toggle);
        } else {
            const spacer = document.createElement("span");
            spacer.className = "xmind-toggle-spacer";
            header.appendChild(spacer);
        }

        // 主题标题
        const title = document.createElement("span");
        title.className = "xmind-topic-title";
        title.textContent = topic.title;
        title.title = topic.title;
        header.appendChild(title);

        // 标注（labels）
        if (topic.labels && topic.labels.length > 0) {
            const labelsContainer = document.createElement("span");
            labelsContainer.className = "xmind-labels";
            topic.labels.forEach(label => {
                const labelEl = document.createElement("span");
                labelEl.className = "xmind-label";
                labelEl.textContent = label;
                labelsContainer.appendChild(labelEl);
            });
            header.appendChild(labelsContainer);
        }

        topicEl.appendChild(header);

        // 笔记（notes）
        if (topic.notes) {
            const notes = document.createElement("div");
            notes.className = "xmind-notes";
            notes.textContent = topic.notes;
            topicEl.appendChild(notes);
        }

        parentElement.appendChild(topicEl);

        // 子主题容器
        if (hasChildren && isExpanded) {
            const childrenContainer = document.createElement("div");
            childrenContainer.className = "xmind-children";
            topic.children.forEach(child => {
                this._renderTopic(child, childrenContainer, depth + 1);
            });
            parentElement.appendChild(childrenContainer);
        }
    }

    /**
     * 切换节点展开/折叠
     */
    _toggleNode(topicId) {
        if (this.expandedNodes.has(topicId)) {
            this.expandedNodes.delete(topicId);
        } else {
            this.expandedNodes.add(topicId);
        }
        this._switchSheet(this.currentSheet.id); // 重新渲染
    }

    /**
     * 全部展开
     */
    _expandAll() {
        const allTopicIds = new Set();
        const traverse = (topic) => {
            allTopicIds.add(topic.id);
            if (topic.children) {
                topic.children.forEach(traverse);
            }
        };
        if (this.currentSheet && this.currentSheet.rootTopic) {
            traverse(this.currentSheet.rootTopic);
        }
        this.expandedNodes = allTopicIds;
        this._switchSheet(this.currentSheet.id);
    }

    /**
     * 全部折叠
     */
    _collapseAll() {
        this.expandedNodes.clear();
        this._switchSheet(this.currentSheet.id);
    }

    /**
     * 清理资源
     */
    destroy() {
        this.container.innerHTML = "";
        this.sheets = [];
        this.currentSheet = null;
        this.expandedNodes.clear();
    }
}

// 导出到全局
window.MMFBXmindViewer = MMFBXmindViewer;
