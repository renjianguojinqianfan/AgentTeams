请评估以下主岗应答：

陪练剧本（客户问题）：{question}
考察维度：{category}
主岗应答：{answer}

请返回 JSON 格式：
- score: 0-10 整数评分
- feedback: 一句话评价（50 字以内，指出优点与不足）
- shouldFollowUp: 是否建议追问（true/false）
- followUpSuggestion: 追问建议方向（若 shouldFollowUp 为 true）