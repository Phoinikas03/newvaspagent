import os
import asyncio
from pathlib import Path
from typing import Dict, Any
# ==========================================
# 获取 POSCAR (MPRester 异步优化版)
# ==========================================
def _fetch_and_save_structure_sync(mp_id: str, output_filename: Path, api_key: str):
    """(同步函数) 实际执行网络请求和文件写入的阻塞任务"""
    from mp_api.client import MPRester
    
    with MPRester(api_key) as mpr:
        structure = mpr.get_structure_by_material_id(mp_id)
        if structure is None:
            raise ValueError(f"Structure not found for {mp_id}")
            
        # 写入文件同样是阻塞 I/O，一起放在这里处理
        structure.to(fmt="poscar", filename=str(output_filename))

async def get_poscar_impl(mp_id: str, workspace_dir: str) -> Dict[str, Any]:
    """(异步接口) 供 Tool 调用的核心逻辑"""
    workdir = Path(workspace_dir)
    api_key = os.getenv("MP_API")
    
    if not api_key:
        return {"content": [{"type": "text", "text": "Error: MP_API environment variable is missing."}]}
        
    workdir.mkdir(parents=True, exist_ok=True)
    output_filename = (workdir / f"POSCAR_{mp_id}").resolve()
    
    try:
        # 将同步网络请求和磁盘读写推送到后台线程
        await asyncio.to_thread(_fetch_and_save_structure_sync, mp_id, output_filename, api_key)
        return {"content": [{"type": "text", "text": f"POSCAR_{mp_id} saved to {output_filename}"}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {str(e)}"}]}


# ==========================================
# 设置 VASP 输入文件 (POTCAR 智能回退增强版)
# ==========================================
def _setup_vasp_inputs_sync(poscar_path: Path, incar_path: Path, work_dir: Path, kpoints_density: int) -> str:
    """(同步函数) 实际执行文件读写、Pymatgen 对象实例化及文件生成的阻塞任务"""
    from pymatgen.core import Structure
    from pymatgen.io.vasp import Incar, Kpoints, Potcar, PotcarSingle
    
    # 确保目标工作目录存在
    work_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. 读取原始结构和自定义 INCAR
    structure = Structure.from_file(str(poscar_path))
    incar = Incar.from_file(str(incar_path))
    
    # 2. K 点：若 INCAR 已含 KSPACING，则由 VASP 从 INCAR 生成网格，不写 KPOINTS 文件
    use_kspacing = incar.get("KSPACING") is not None
    
    # 3. 自动生成 POTCAR (智能 Fallback 机制)
    # 获取 POSCAR 中按顺序排列的元素种类
    species = [str(sp) for sp in structure.types_of_specie]
    potcar_symbols = []
    
    for sym in species:
        best_sym = None
        # 按计算代价从低到高进行智能尝试 (标准 -> _pv -> _sv -> _d -> _h)
        for suffix in ["", "_pv", "_sv", "_d", "_h"]:
            try:
                test_sym = f"{sym}{suffix}"
                # 尝试读取该符号对应的 POTCAR
                PotcarSingle.from_symbol_and_functional(test_sym, "PBE")
                best_sym = test_sym
                break # 找到最轻量且存在的一个，直接跳出
            except Exception:
                continue
                
        if not best_sym:
            raise ValueError(f"Cannot find any PBE POTCAR for element '{sym}' (tried '', '_pv', '_sv', etc.). Please check PMG_VASP_PSP_DIR.")
            
        potcar_symbols.append(best_sym)
        
    potcar = Potcar(symbols=potcar_symbols, functional="PBE")
    
    # 4. 将所有文件写入目标工作目录
    structure.to(fmt="poscar", filename=str(work_dir / "POSCAR"))
    incar.write_file(str(work_dir / "INCAR"))
    kpath = work_dir / "KPOINTS"
    if use_kspacing:
        if kpath.exists():
            kpath.unlink()
        k_mesh_info = f"K mesh from INCAR KSPACING={incar.get('KSPACING')} (no KPOINTS file)"
    else:
        kpoints = Kpoints.automatic_density(structure, kpoints_density)
        kpoints.write_file(str(kpath))
        k_mesh_info = f"KPOINTS from automatic_density={kpoints_density}"
    potcar.write_file(str(work_dir / "POTCAR"))
    
    return (
        f"Successfully generated POSCAR, INCAR, and POTCAR in {work_dir}\n"
        f"{k_mesh_info}\n"
        f"(Used POTCARs: {', '.join(potcar_symbols)})"
    )


async def setup_vasp_inputs_impl(poscar_path: str, incar_path: str, workspace_dir: str, kpoints_density: int = 100) -> Dict[str, Any]:
    """(异步接口) 供 Tool 调用的核心逻辑：基于自定义 INCAR 和 POSCAR 自动生成全套 VASP 输入文件"""
    work_dir = Path(workspace_dir).resolve()
    poscar_file = Path(poscar_path).resolve()
    incar_file = Path(incar_path).resolve()
    
    if not poscar_file.exists():
        return {"content": [{"type": "text", "text": f"Error: The source POSCAR file was not found at {poscar_file}"}]}
    if not incar_file.exists():
        return {"content": [{"type": "text", "text": f"Error: The source INCAR file was not found at {incar_file}"}]}
        
    try:
        success_msg = await asyncio.to_thread(
            _setup_vasp_inputs_sync, 
            poscar_file, 
            incar_file, 
            work_dir, 
            kpoints_density
        )
        return {"content": [{"type": "text", "text": success_msg}]}
        
    except Exception as e:
        error_msg = f"Error during VASP input generation: {str(e)}"
        if "No POTCAR" in str(e) or "VASP_PSP_DIR" in str(e):
            error_msg += "\n(Hint: Ensure PMG_VASP_PSP_DIR is configured in your environment or ~/.pmgrc.yaml)"
        return {"content": [{"type": "text", "text": error_msg}]}


# ==========================================
# DuckDuckGo 搜索
# ==========================================
async def duckduckgo_search_impl(query: str, max_results: int = 10) -> Dict[str, Any]:
    try:
        from ddgs import DDGS
        def _run_search():
            with DDGS() as ddgs:
                return list(ddgs.text(query, max_results=max_results))
        results = await asyncio.to_thread(_run_search)
        if not results:
            return {"content": [{"type": "text", "text": "No results found! Try a less restrictive/shorter query."}]}
        postprocessed_results = [f"[{res['title']}]({res['href']})\n{res['body']}" for res in results]
        final_text = "## Search Results\n\n" + "\n\n".join(postprocessed_results)
        return {"content": [{"type": "text", "text": final_text}]}
    except ImportError:
        return {"content": [{"type": "text", "text": "Error: You must install `ddgs` (pip install duckduckgo-search)."}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {str(e)}"}]}

# ==========================================
# Google 搜索
# ==========================================
def _google_search_sync(query: str, provider: str, api_key: str) -> dict:
    import requests
    if provider == "serpapi":
        base_url = "https://serpapi.com/search.json"
        params = {"q": query, "api_key": api_key, "engine": "google", "google_domain": "google.com"}
    else:
        base_url = "https://google.serper.dev/search"
        params = {"q": query, "api_key": api_key}
    response = requests.get(base_url, params=params, timeout=15)
    response.raise_for_status()
    return response.json()

async def google_search_impl(query: str, provider: str = "serper") -> Dict[str, Any]:
    api_key = os.getenv(f"{provider.upper()}_API_KEY")
    if not api_key:
        return {"content": [{"type": "text", "text": f"Error: Missing API key. Make sure {provider.upper()}_API_KEY is in your env variables."}]}
    try:
        results = await asyncio.to_thread(_google_search_sync, query, provider, api_key)
        organic_key = "organic_results" if provider == "serpapi" else "organic"
        if organic_key not in results or len(results[organic_key]) == 0:
            return {"content": [{"type": "text", "text": f"No results found for '{query}'. Try with a more general query."}]}
        web_snippets = []
        for idx, page in enumerate(results[organic_key]):
            title = page.get("title", "No Title")
            link = page.get("link", "")
            snippet = page.get("snippet", "")
            web_snippets.append(f"{idx + 1}. [{title}]({link})\n{snippet}")
        final_text = "## Search Results\n\n" + "\n\n".join(web_snippets)
        return {"content": [{"type": "text", "text": final_text}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {str(e)}"}]}

# ==========================================
# 网页浏览工具
# ==========================================
def _visit_webpage_sync(url: str) -> str:
    import requests
    import re
    import urllib3
    from markdownify import markdownify
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    response = requests.get(url, headers=headers, timeout=20, verify=False)
    response.raise_for_status()
    markdown_content = markdownify(response.text).strip()
    markdown_content = re.sub(r"\n{3,}", "\n\n", markdown_content)
    return markdown_content

async def visit_webpage_impl(url: str, max_output_length: int = 50000) -> Dict[str, Any]:
    try:
        import markdownify  
    except ImportError:
        return {"content": [{"type": "text", "text": "Error: You must install `markdownify` (pip install markdownify)."}]}
    import requests
    try:
        markdown_content = await asyncio.to_thread(_visit_webpage_sync, url)
        if len(markdown_content) > max_output_length:
            markdown_content = markdown_content[:max_output_length] + \
                f"\n\n..._This content has been truncated to stay below {max_output_length} characters_...\n"
        return {"content": [{"type": "text", "text": markdown_content}]}
    except requests.exceptions.Timeout:
        return {"content": [{"type": "text", "text": "Error: The request timed out. Please try again later or check the URL."}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error fetching the webpage: {str(e)}"}]}

# ==========================================
# 学术开源文献检索 (arXiv API)
# ==========================================
def _arxiv_search_sync(query: str, max_results: int) -> list:
    import requests
    import xml.etree.ElementTree as ET
    base_url = "http://export.arxiv.org/api/query"
    params = {
        "search_query": query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending"
    }
    response = requests.get(base_url, params=params, timeout=15)
    response.raise_for_status()
    root = ET.fromstring(response.text)
    ns = {'atom': 'http://www.w3.org/2005/Atom'}
    papers = []
    for entry in root.findall('atom:entry', ns):
        title = entry.find('atom:title', ns).text.replace('\n', ' ').strip()
        summary = entry.find('atom:summary', ns).text.replace('\n', ' ').strip()
        pdf_link = ""
        for link in entry.findall('atom:link', ns):
            if link.attrib.get('title') == 'pdf':
                pdf_link = link.attrib.get('href')
                break
        papers.append({
            "title": title,
            "summary": summary,
            "pdf_link": pdf_link
        })
    return papers

async def arxiv_search_impl(query: str, max_results: int = 5) -> Dict[str, Any]:
    try:
        papers = await asyncio.to_thread(_arxiv_search_sync, query, max_results)
        if not papers:
            return {"content": [{"type": "text", "text": f"No open-access papers found for query: '{query}'"}]}
        snippets = []
        for idx, paper in enumerate(papers):
            pdf_url = paper["pdf_link"] + ".pdf" if paper["pdf_link"] else "No PDF available"
            snippets.append(
                f"### {idx + 1}. {paper['title']}\n"
                f"**PDF Download Link**: {pdf_url}\n"
                f"**Abstract**: {paper['summary'][:500]}...\n"
            )
        final_text = "## Academic Search Results (Open Access)\n\n" + "\n\n".join(snippets)
        return {"content": [{"type": "text", "text": final_text}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error searching academic papers: {str(e)}"}]}

# ==========================================
# Semantic Scholar 学术文献搜索
# ==========================================
import requests

def _semanticscholar_search_sync(query: str, max_results: int) -> list:
    base_url = "https://api.semanticscholar.org/graph/v1/paper/search/bulk"
    params = {
        "query": query,
        "fields": "title,abstract,year,openAccessPdf"
    }
    headers = {}
    response = requests.get(base_url, params=params, headers=headers, timeout=15)
    response.raise_for_status()
    data = response.json()
    papers = []
    for item in data.get('data', []):
        if len(papers) >= max_results:
            break
        title = item.get('title') or "Untitled"
        abstract = item.get('abstract') or "No abstract available"
        year = item.get('year') or "Unknown year"
        pdf_link = ""
        oa_pdf = item.get('openAccessPdf')
        if oa_pdf and isinstance(oa_pdf, dict):
            pdf_link = oa_pdf.get('url', "")
        papers.append({
            "title": title,
            "abstract": abstract,
            "year": year,
            "pdf_link": pdf_link
        })
    return papers

async def semanticscholar_search_impl(query: str, max_results: int = 5) -> Dict[str, Any]:
    try:
        papers = await asyncio.to_thread(_semanticscholar_search_sync, query, max_results)
        if not papers:
            return {"content": [{"type": "text", "text": f"No papers found for query: '{query}'"}]}
        snippets = []
        for idx, paper in enumerate(papers):
            pdf_url = paper["pdf_link"] if paper["pdf_link"] else "No open-access PDF available"
            abstract_text = paper['abstract']
            if len(abstract_text) > 500:
                abstract_text = abstract_text[:500] + "..."
            snippets.append(
                f"### {idx + 1}. {paper['title']} ({paper['year']})\n"
                f"PDF Download Link: {pdf_url}\n"
                f"Abstract: {abstract_text}\n"
            )
        final_text = "## Semantic Scholar Bulk Search Results\n\n" + "\n\n".join(snippets)
        return {"content": [{"type": "text", "text": final_text}]}
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            error_msg = "Rate limit exceeded (429). You are sharing the unauthenticated API pool. Please configure an API Key (1 req/sec limit)."
        elif e.response.status_code == 400:
            error_msg = f"Bad Request (400): Check your search query parameters. Details: {e.response.text}"
        else:
            error_msg = f"HTTP Error {e.response.status_code}: {str(e)}"
        return {"content": [{"type": "text", "text": error_msg}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error searching Semantic Scholar: {str(e)}"}]}