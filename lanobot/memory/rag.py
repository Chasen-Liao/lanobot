"""RAG 节点 - 检索增强生成."""

from typing import Optional, Protocol
from pathlib import Path

from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore
from langchain_core.embeddings import Embeddings


class RAGRetriever(Protocol):
    """RAG 检索器协议."""

    async def retrieve(self, query: str, k: int = 5) -> list[Document]:
        """检索相关文档.

        Args:
            query: 查询字符串
            k: 返回文档数量

        Returns:
            相关文档列表
        """
        ...


class InMemoryRAG:
    """内存版 RAG 检索器（简化版，无向量依赖）.

    适用于小规模知识库，使用简单的关键词匹配。
    生产环境建议使用 FAISS、Milvus 等向量数据库。
    """

    def __init__(
        self,
        documents: Optional[list[Document]] = None,
    ):
        """初始化 RAG 检索器.

        Args:
            documents: 初始文档列表
        """
        self._documents = documents or []

    async def retrieve(self, query: str, k: int = 5) -> list[Document]:
        """检索相关文档（简单关键词匹配）.

        Args:
            query: 查询字符串
            k: 返回文档数量

        Returns:
            相关文档列表
        """
        if not self._documents:
            return []

        query_lower = query.lower()
        # 简单评分：包含查询词的文档得分更高
        scored = []
        for doc in self._documents:
            content = doc.page_content.lower()
            # 计算匹配关键词数量
            keywords = query_lower.split()
            score = sum(1 for kw in keywords if kw in content)
            if score > 0:
                scored.append((score, doc))

        # 按分数排序，返回 top k
        scored.sort(reverse=True, key=lambda x: x[0])
        return [doc for _, doc in scored[:k]]

    def add_documents(self, documents: list[Document]) -> None:
        """添加文档到知识库.

        Args:
            documents: 要添加的文档列表
        """
        self._documents.extend(documents)

    def get_context(self, query: str, k: int = 3) -> str:
        """获取检索上下文.

        Args:
            query: 查询字符串
            k: 返回文档数量

        Returns:
            格式化的上下文字符串
        """
        import asyncio
        # 同步调用 async 方法
        docs = asyncio.run(self.retrieve(query, k=k))
        if not docs:
            return ""

        contexts = []
        for i, doc in enumerate(docs, 1):
            source = doc.metadata.get("source", "unknown")
            content = doc.page_content[:500]  # 限制长度
            contexts.append(f"[{i}] {source}:\n{content}")

        return "\n\n".join(contexts)


class RAGNode:
    """RAG 节点 - 用于 LangGraph 图中.

    在 LLM 调用前自动检索相关文档并注入上下文。
    """

    def __init__(
        self,
        retriever: Optional[RAGRetriever] = None,
        k: int = 3,
        include_sources: bool = True,
    ):
        """初始化 RAG 节点.

        Args:
            retriever: RAG 检索器
            k: 检索文档数量
            include_sources: 是否包含来源信息
        """
        self.retriever = retriever
        self.k = k
        self.include_sources = include_sources

    async def retrieve(self, query: str) -> str:
        """检索相关文档.

        Args:
            query: 查询字符串

        Returns:
            格式化的上下文字符串
        """
        if not self.retriever:
            return ""

        docs = await self.retriever.retrieve(query, k=self.k)
        if not docs:
            return ""

        contexts = []
        for i, doc in enumerate(docs, 1):
            content = doc.page_content[:500]
            if self.include_sources:
                source = doc.metadata.get("source", "unknown")
                contexts.append(f"[{i}] {source}:\n{content}")
            else:
                contexts.append(content)

        return "\n\n".join(contexts)

    def build_context_message(self, query: str, context: str) -> str:
        """构建带有上下文的系统提示词.

        Args:
            query: 用户查询
            context: 检索到的上下文

        Returns:
            格式化的系统消息
        """
        if not context:
            return ""

        return f"""<context>
{context}
</context>

根据以上上下文回答用户问题。如果上下文不相关，请忽略并基于你自身的知识回答。"""


# 便捷函数：从文件加载知识库
def load_knowledge_from_files(
    directory: Path,
    glob_pattern: str = "**/*.txt",
    chunk_size: int = 1000,
) -> list[Document]:
    """从目录加载知识库文件（简化版，不依赖 text-splitters）.

    Args:
        directory: 文件目录
        glob_pattern: 文件匹配模式
        chunk_size: 分块大小

    Returns:
        Document 列表
    """
    documents = []

    for file_path in directory.glob(glob_pattern):
        if file_path.is_file():
            content = file_path.read_text(encoding="utf-8")
            # 简单分块
            for i in range(0, len(content), chunk_size):
                chunk = content[i:i + chunk_size]
                if chunk.strip():
                    documents.append(Document(
                        page_content=chunk,
                        metadata={"source": str(file_path.name)}
                    ))

    return documents


def create_rag_node(
    knowledge_dir: Optional[Path] = None,
    k: int = 3,
) -> RAGNode:
    """创建 RAG 节点（便捷函数）.

    Args:
        knowledge_dir: 知识库目录（会自动加载文件）
        k: 检索文档数量

    Returns:
        RAGNode 实例

    Examples:
        >>> rag_node = create_rag_node(
        ...     knowledge_dir=Path("./knowledge"),
        ...     k=5
        ... )
        >>> context = await rag_node.retrieve("如何配置lanobot?")
    """
    retriever = None

    if knowledge_dir and knowledge_dir.exists():
        docs = load_knowledge_from_files(knowledge_dir)
        if docs:
            retriever = InMemoryRAG(documents=docs)

    # 如果没有知识库，也创建空节点（不报错）
    return RAGNode(retriever=retriever, k=k)