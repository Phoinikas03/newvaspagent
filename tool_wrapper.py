from tool import duckduckgo_search_impl, get_poscar_impl, visit_webpage_impl, google_search_impl, arxiv_search_impl, setup_vasp_inputs_impl, run_vasp_impl, semanticscholar_search_impl
from claude_agent_sdk import tool
from typing import Dict, Any, Optional

# ==========================================
# POSCAR 获取工具
# ==========================================
def poscar_tool(workspace_dir: str):
    """闭包函数：注入 workspace_dir 并返回组装好的 Tool"""
    
    @tool(
        name="get_poscar_from_md", 
        description="Get POSCAR from Materials Project by Materials Project ID, and save it to the workspace.", 
        input_schema={"mp_id": str}
    )
    async def get_poscar_from_md(args: Dict[str, Any]) -> Dict[str, Any]:
        # 仅负责参数提取和转发
        return await get_poscar_impl(
            mp_id=args["mp_id"], 
            workspace_dir=workspace_dir
        )
            
    return get_poscar_from_md

# ==========================================
# VASP 输入文件生成工具
# ==========================================
def setup_vasp_inputs_tool(workspace_dir: str, default_kpoints_density: int = 100):
    """闭包函数：注入 workspace_dir 和默认网格密度配置并返回组装好的 Tool"""
    
    @tool(
        name="setup_vasp_inputs", 
        description=(
            "Generates full VASP input files (KPOINTS, POTCAR, POSCAR, INCAR) in the workspace directory based on a provided POSCAR file path and a custom INCAR file path. The default kpoints density is 100."
        ), 
        input_schema={
            "poscar_path": str, 
            "incar_path": str, 
            "kpoints_density": Optional[int]  # 允许大模型根据需要调整 K 点密度
        }
    )
    async def setup_vasp_inputs(args: Dict[str, Any]) -> Dict[str, Any]:
        # 提取参数，如果大模型没有传入 kpoints_density，则使用外部注入的默认值
        density = int(args.get("kpoints_density", default_kpoints_density))
        
        # 仅负责参数提取和转发
        return await setup_vasp_inputs_impl(
            poscar_path=args["poscar_path"], 
            incar_path=args["incar_path"], 
            workspace_dir=workspace_dir,
            kpoints_density=density
        )
            
    return setup_vasp_inputs
def run_vasp_tool(workspace_dir: str):
    """闭包函数：注入 workspace_dir 配置并返回组装好的 Tool"""
    
    @tool(
        name="run_vasp",
        description="Run VASP calculation in the workspace directory. The default number of processes is 4.",
        input_schema={"num_process": Optional[int]}
    )
    async def run_vasp(args: Dict[str, Any]) -> Dict[str, Any]:
        np = int(args.get("num_process", 4))
        return await run_vasp_impl(
            workspace_dir=workspace_dir,
            num_process=np
        )

    return run_vasp
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
def google_search_tool(provider: str = "serpapi"):
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