"""
查询重写模块

优化点:
1. HyDE (Hypothetical Document Embeddings): 让 LLM 生成假设性答案，用答案的 embedding 检索
2. 查询扩展：将简短查询扩展为更丰富的描述
3. 多查询融合：生成多个变体查询，合并检索结果

这些技术能显著提升 RAG 的召回率，特别是对于简短或模糊的查询
"""
from __future__ import annotations

import json

from app.llm.client import get_current_model_name


class QueryRewriter:
    """查询重写器"""

    def __init__(self, llm_client):
        self.client = llm_client

    async def hyde_rewrite(
        self, query: str
    ) -> str:
        """
        HyDE: Hypothetical Document Embeddings

        让 LLM 根据查询生成一个假设性的答案文档，
        然后用这个假设文档的 embedding 去检索

        原理: 答案和答案在向量空间中更接近，比问题和答案更接近
        """
        prompt = f"""请根据以下问题，生成一段假设性的故障排查答案。
要求：
1. 包含可能的原因、症状、解决方案
2. 使用技术术语
3. 200-300 字
4. 直接输出答案，不要加前缀

问题: {query}

假设性答案:"""

        try:
            response = await self.client.chat.completions.create(
                model=get_current_model_name(),
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                temperature=0.3,
                max_tokens=400,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"[QueryRewriter] HyDE 失败: {e}")
            return query

    async def expand_query(
        self, query: str
    ) -> list[str]:
        """
        查询扩展：生成多个查询变体

        将一个查询扩展为 3 个不同角度的变体，
        用于多路检索后融合
        """
        prompt = f"""请将以下查询扩展为 3 个不同角度的搜索查询，用于知识库检索。
要求：
1. 每个查询独立成行
2. 保持技术性
3. 覆盖不同方面（症状、原因、解决方案）
4. 直接输出查询，不要编号

原始查询: {query}

扩展查询:"""

        try:
            response = await self.client.chat.completions.create(
                model=get_current_model_name(),
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                temperature=0.3,
                max_tokens=200,
            )
            content = response.choices[0].message.content.strip()
            # 按行分割，过滤空行
            queries = [
                q.strip()
                for q in content.split("\n")
                if q.strip()
            ]
            # 限制最多 3 个
            return queries[:3]
        except Exception as e:
            print(f"[QueryRewriter] 查询扩展失败: {e}")
            return [query]