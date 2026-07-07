---
name: session-memory-save
description: Saves or appends the question and answer summary of the current session to the SessionMemory directory in markdown format after the AI response is completed.
---
# Session Memory Save Skill

每次 AI 回答/任务完成前，将当前对话的问题 and 回答总结记录或追加到项目根目录 `SessionMemory` 文件夹中的当日 session 文件。

优先遵循仓库根目录 [AGENTS.md](file:///d:/Self/RoyDsa/AGENTS.md)。

## Usage

此 skill 由系统或 `AGENTS.md` 规则在每次对话结束前自动触发执行。

## Instructions

在准备结束当前 turn 并向用户输出最终回答前，执行以下步骤：

### Step 1: 检查 SessionMemory 文件夹
1. 检查项目根目录下是否存在 `SessionMemory` 文件夹。如果不存在，使用 `write_to_file` 工具创建它。

### Step 2: 查找已有的 Session 文件
1. 对话的“第一个问题”指的是本对话（Session）的最开始的那个用户输入。可以通过阅读当前的对话上下文（Context）来获取该对话的第一个问题以及前面的问答内容。
2. 列出 `SessionMemory` 目录下的所有文件，查找文件名以当前日期（`YYYYMMDD` 格式）开头、且后缀为 `.md` 的文件。
3. 对每个匹配的文件，读取其第一行标题（`# 标题`），判断是否与本对话的第一个问题的语义基本一致。
4. 如果语义一致，则认为找到了该对话的已有 session 文件。

### Step 3: 追加或新建文件
- **如果找到已有的 session 文件**：
  1. 读取该文件内容，判断本次【新增的问答】（即当前最新一轮问答）是否已被记录。
  2. 若未被记录，使用 `replace_file_content` 或 `multi_replace_file_content` 将新问答追加到文件末尾。
  3. 追加的格式为：
     ```markdown
     
     ---
     
     ## Q: 用户问题
     
     ## A: 回答总结
     
     ```
     其中“用户问题”为本轮的提问，“回答总结”为对本轮回答的简明总结。

- **如果没有找到已有的 session 文件**（即本次对话是该 session 的第一次记录）：
  1. 确定文件名格式：`YYYYMMDDHHmm_问题摘要.md`。
     - 时间取当前时间（例如从 `current local time` 获取的 `YYYYMMDDHHmm`）。
     - 问题摘要取自用户的第一个问题。如果其中包含文件名非法字符（如 `: / \ * ? " < > |` 等），则将问题简短总结为合法的中文/英文数字下划线文件名。
  2. 确定文件内容，格式如下：
     ```markdown
     # 用户的第一个问题

     ## Q: 用户问题

     ## A: 回答总结
     ```
  3. 使用 `write_to_file` 创建该文件到 `SessionMemory/` 目录下。

## 注意事项
- 只总结有实质内容的对话，不要包含 session-memory-save skill 本身的执行过程或元数据。
- 关键原则：同一个 session 只对应一个文件，后续问答追加而非新建。
