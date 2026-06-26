from .tool import duckduckgo_search_impl, visit_webpage_impl, google_search_impl, arxiv_search_impl, setup_vasp_inputs_impl, semanticscholar_search_impl
from claude_agent_sdk import tool
from typing import Dict, Any, Optional

# ==========================================
# VASP 输入文件生成工具
# ==========================================
def setup_vasp_inputs_tool(workspace_dir: str, default_kpoints_density: int = 100):
    """闭包函数：注入 workspace_dir 和默认网格密度配置并返回组装好的 Tool"""
    
    @tool(
        name="setup_vasp_inputs", 
        description=(
            "Generates VASP inputs (POTCAR, POSCAR copy, INCAR) in the workspace. "
            "If the INCAR contains KSPACING, k-points come from INCAR only and no KPOINTS file is written. "
            "Otherwise writes KPOINTS via automatic_density; kpoints_density defaults to 100. "
            'Optional potcar_overrides maps POSCAR element symbols to exact PBE POTCAR symbols as a JSON object '
            '(for example {"Cr": "Cr_pv"}). Pass this when the user explicitly requests a POTCAR variant; '
            "explicit overrides are validated and do not fall back. JSON object strings are accepted for compatibility."
        ), 
        input_schema={
            "poscar_path": str, 
            "incar_path": str, 
            "kpoints_density": Optional[int],  # 允许大模型根据需要调整 K 点密度
            "potcar_overrides": Optional[Dict[str, str]],
        }
    )
    async def setup_vasp_inputs(args: Dict[str, Any]) -> Dict[str, Any]:
        # 提取参数，如果大模型没有传入 kpoints_density，则使用外部注入的默认值
        density = int(args.get("kpoints_density", default_kpoints_density))
        potcar_overrides = args.get("potcar_overrides") or None
        
        # 仅负责参数提取和转发
        return await setup_vasp_inputs_impl(
            poscar_path=args["poscar_path"], 
            incar_path=args["incar_path"], 
            workspace_dir=workspace_dir,
            kpoints_density=density,
            potcar_overrides=potcar_overrides,
        )
            
    return setup_vasp_inputs


# ==========================================
# DuckDuckGo 搜索工具
# ==========================================
def duckduckgo_search_tool(max_results: int = 10):
    """闭包函数：注入 max_results 配置并返回组装好的 Tool"""
    
    @tool(
        name="duckduckgo_search",
        description="Performs a DuckDuckGo web search based on your query and returns the top search results.",
        input_schema={"query": str},
    )
    async def duckduckgo_search(args: Dict[str, Any]) -> Dict[str, Any]:
        # 仅负责参数提取和转发
        return await duckduckgo_search_impl(
            query=args["query"], 
            max_results=max_results
        )

    return duckduckgo_search


# ==========================================
# Google 搜索工具
# ==========================================
def google_search_tool(provider: str = "serper"):
    """闭包函数：注入 provider 配置并返回组装好的 Tool"""
    
    @tool(
        name="google_search", 
        description="Performs a Google web search for your query and returns a string of the top search results.", 
        input_schema={"query": str}
    )
    async def google_search(args: Dict[str, Any]) -> Dict[str, Any]:
        # 仅负责参数提取和转发
        return await google_search_impl(
            query=args["query"], 
            provider=provider
        )
            
    return google_search


# ==========================================
# 网页浏览工具
# ==========================================
def visit_webpage_tool(max_output_length: int = 40000):
    """闭包函数：注入 max_output_length 配置并返回组装好的 Tool"""
    
    @tool(
        name="visit_webpage", 
        description="Visits a webpage at the given url and reads its content as a markdown string. Use this to browse webpages.", 
        input_schema={"url": str}
    )
    async def visit_webpage(args: Dict[str, Any]) -> Dict[str, Any]:
        # 仅负责参数提取和转发
        return await visit_webpage_impl(
            url=args["url"], 
            max_output_length=max_output_length
        )

    return visit_webpage

# ==========================================
# Tool 包装器：Arxiv学术文献搜索
# ==========================================
def arxiv_search_tool(max_results: int = 5):
    """闭包函数：注入 max_results 配置并返回组装好的学术搜索 Tool"""
    
    @tool(
        name="arxiv_search", 
        description=(
            "Search for open-access academic papers, especially in computational materials, physics, and computer science. "
            "Returns the paper title, abstract, and a direct PDF download link."
        ), 
        input_schema={"query": str}
    )
    async def arxiv_search(args: Dict[str, Any]) -> Dict[str, Any]:
        return await arxiv_search_impl(
            query=args["query"], 
            max_results=max_results
        )

    return arxiv_search

# ==========================================
# Tool 包装器：Semantic Scholar 学术文献搜索
# ==========================================
def semanticscholar_search_tool(max_results: int = 5):
    """闭包函数：注入 max_results 配置并返回组装好的 Semantic Scholar 搜索 Tool"""
    
    @tool(
        name="semanticscholar_search", 
        description=(
            "Search for academic papers across all scientific fields using the Semantic Scholar API. "
            "Supports advanced search syntax (e.g., '\"exact phrase\" +required -excluded'). "
            "Returns the paper title, publication year, abstract, and an open-access PDF download link if available."
        ), 
        input_schema={"query": str}
    )
    async def semanticscholar_search(args: Dict[str, Any]) -> Dict[str, Any]:
        # 仅负责参数提取和转发
        return await semanticscholar_search_impl(
            query=args["query"], 
            max_results=max_results
        )

    return semanticscholar_search
