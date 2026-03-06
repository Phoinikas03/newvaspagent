import os
import asyncio
from pathlib import Path
from typing import Dict, Any

from datetime import datetime
import subprocess

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
        # 【关键优化】将同步网络请求和磁盘读写推送到后台线程
        await asyncio.to_thread(_fetch_and_save_structure_sync, mp_id, output_filename, api_key)
        return {"content": [{"type": "text", "text": f"POSCAR_{mp_id} saved to {output_filename}"}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {str(e)}"}]}

# ==========================================
# 设置 VASP 输入文件
# ==========================================
def _setup_vasp_inputs_sync(poscar_path: Path, incar_path: Path, work_dir: Path, kpoints_density: int) -> str:
    """(同步函数) 实际执行文件读写、Pymatgen 对象实例化及文件生成的阻塞任务"""
    from pymatgen.core import Structure
    from pymatgen.io.vasp import Incar, Kpoints, Potcar
    
    # 确保目标工作目录存在
    work_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. 读取原始结构和自定义 INCAR
    structure = Structure.from_file(str(poscar_path))
    incar = Incar.from_file(str(incar_path))
    
    # 2. 自动生成 KPOINTS (基于原子密度)
    kpoints = Kpoints.automatic_density(structure, kpoints_density)
    
    # 3. 自动生成 POTCAR (基于 PBE 泛函)
    # ⚠️ 强依赖：此步骤需要运行环境中已正确配置 PMG_VASP_PSP_DIR
    potcar = Potcar(symbols=structure.symbol_set, functional="PBE")
    
    # 4. 将所有文件写入目标工作目录
    structure.to(fmt="poscar", filename=str(work_dir / "POSCAR"))
    incar.write_file(str(work_dir / "INCAR"))
    kpoints.write_file(str(work_dir / "KPOINTS"))
    potcar.write_file(str(work_dir / "POTCAR"))
    
    return f"Successfully generated POSCAR, INCAR, KPOINTS, and POTCAR in {work_dir}"


async def setup_vasp_inputs_impl(poscar_path: str, incar_path: str, workspace_dir: str, kpoints_density: int = 100) -> Dict[str, Any]:
    """(异步接口) 供 Tool 调用的核心逻辑：基于自定义 INCAR 和 POSCAR 自动生成全套 VASP 输入文件"""
    
    # 将输入路径转换为标准的 Path 对象并解析绝对路径，避免相对路径带来的异常
    work_dir = Path(workspace_dir).resolve()
    poscar_file = Path(poscar_path).resolve()
    incar_file = Path(incar_path).resolve()
    
    # 基础校验：提早暴露文件丢失问题，避免陷入深层报错
    if not poscar_file.exists():
        return {"content": [{"type": "text", "text": f"Error: The source POSCAR file was not found at {poscar_file}"}]}
    if not incar_file.exists():
        return {"content": [{"type": "text", "text": f"Error: The source INCAR file was not found at {incar_file}"}]}
        
    try:
        # 【关键优化】使用 asyncio.to_thread 将纯净的、阻塞的 Pymatgen 处理逻辑推送到后台线程
        success_msg = await asyncio.to_thread(
            _setup_vasp_inputs_sync, 
            poscar_file, 
            incar_file, 
            work_dir, 
            kpoints_density
        )
        return {"content": [{"type": "text", "text": success_msg}]}
        
    except Exception as e:
        # 捕获可能出现的 Pymatgen 错误（例如环境变量未配置导致找不到 POTCAR）
        error_msg = f"Error during VASP input generation: {str(e)}"
        
        # 针对最常见的 POTCAR 缺失给出明确的修复建议
        if "No POTCAR" in str(e) or "VASP_PSP_DIR" in str(e):
            error_msg += "\n(Hint: Ensure PMG_VASP_PSP_DIR is configured in your environment or ~/.pmgrc.yaml)"
            
        return {"content": [{"type": "text", "text": error_msg}]}

# ==========================================
# 运行 VASP
# ==========================================
def _run_vasp_sync(work_dir: Path, num_process: int) -> str:
    """(同步函数) 实际执行 VASP 计算的阻塞任务，包含日志重定向"""
    
    # 1. 生成时间戳和日志文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    logname = f"log_{timestamp}.txt"
    log_path = work_dir / logname
    
    # 2. 构建 MPI 运行命令
    # 对应 bash 命令: mpirun -n <num_process> vasp_std
    command = ["mpirun", "-n", str(num_process), "vasp_std"]
    
    # 3. 执行子进程并重定向输出
    # 使用追加模式 ("a") 打开文件，stdout=log_file 和 stderr=subprocess.STDOUT 
    # 完美等价于 bash 中的 >> "$logname" 2>&1
    with open(log_path, "a") as log_file:
        process = subprocess.run(
            command,
            cwd=str(work_dir),          # 确保命令在目标工作目录 (workspace_dir) 中执行
            stdout=log_file,            # 标准输出追加到日志文件
            stderr=subprocess.STDOUT,   # 将标准错误 (2) 合并到标准输出 (1)
            text=True                   # 以文本模式处理输出
        )
        
    # 4. 检查进程返回码，非 0 代表 VASP 运行异常崩溃
    if process.returncode != 0:
        raise RuntimeError(f"VASP execution failed with return code {process.returncode}. Please check {logname} for details.")
        
    return f"VASP calculation completed successfully. Log saved to {logname} in {work_dir}"


async def run_vasp_impl(workspace_dir: str, num_process: int = 4) -> Dict[str, Any]:
    """(异步接口) 供 Tool 调用的核心逻辑：基于指定进程数运行 VASP"""
    
    # 解析并获取绝对路径
    work_dir = Path(workspace_dir).resolve()
    
    # 基础校验 1：确保工作目录存在
    if not work_dir.exists() or not work_dir.is_dir():
        return {"content": [{"type": "text", "text": f"Error: The workspace directory was not found at {work_dir}"}]}
        
    # 基础校验 2：提早拦截文件丢失问题，防止 VASP 秒退
    required_files = ["INCAR", "POSCAR", "POTCAR", "KPOINTS"]
    missing_files = [f for f in required_files if not (work_dir / f).exists()]
    if missing_files:
        return {"content": [{"type": "text", "text": f"Error: Cannot run VASP. Missing required input files in workspace: {', '.join(missing_files)}"}]}
        
    try:
        # 【关键设计】使用 asyncio.to_thread 将耗时的 VASP 计算推入后台线程，
        # 确保 VASP 运行期间不会阻塞 MCP Server 的主事件循环
        success_msg = await asyncio.to_thread(
            _run_vasp_sync, 
            work_dir, 
            num_process
        )
        return {"content": [{"type": "text", "text": success_msg}]}
        
    except FileNotFoundError as e:
        # 专门捕获 subprocess 找不到可执行文件 (mpirun 或 vasp_std) 的异常
        error_msg = f"Error: Executable not found. {str(e)}\n"
        error_msg += "(Hint: Ensure 'mpirun' and 'vasp_std' are correctly installed and added to your system PATH.)"
        return {"content": [{"type": "text", "text": error_msg}]}
        
    except Exception as e:
        # 捕获 VASP 运行过程中的报错（如内存溢出、参数错误导致的异常退出）
        error_msg = f"Error during VASP execution: {str(e)}"
        return {"content": [{"type": "text", "text": error_msg}]}

# ==========================================
# DuckDuckGo 搜索
# ==========================================
async def duckduckgo_search_impl(query: str, max_results: int = 10) -> Dict[str, Any]:
    """(异步接口) 供 Tool 调用和测试搜索实现"""
    try:
        from ddgs import DDGS

        def _run_search():
            with DDGS() as ddgs:
                return list(ddgs.text(query, max_results=max_results))

        # 将同步的搜索库调用放入后台线程
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
    """(同步函数) 实际执行 HTTP 请求的阻塞任务"""
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
    """(异步接口) 供 Tool 调用的核心逻辑"""
    api_key = os.getenv(f"{provider.upper()}_API_KEY")
    # api_key = "005bbbfe8fd8c8bd183a6e0b20c1ae08c83001da"
    if not api_key:
        return {"content": [{"type": "text", "text": f"Error: Missing API key. Make sure {provider.upper()}_API_KEY is in your env variables."}]}

    try:
        # 将同步的 HTTP 请求推送到后台线程
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
    """(同步函数) 负责网页抓取和 Markdown 转换的阻塞任务"""
    import requests
    import re
    import urllib3
    from markdownify import markdownify
    
    # 彻底静音 urllib3 的 InsecureRequestWarning 警告（让控制台清爽一点）
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    # 【关键修改】添加常见浏览器的 User-Agent，绕过基础反爬
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    
    # 将 headers 传入请求
    response = requests.get(url, headers=headers, timeout=20, verify=False)
    response.raise_for_status()

    # 转换并清理多余的换行符
    markdown_content = markdownify(response.text).strip()
    markdown_content = re.sub(r"\n{3,}", "\n\n", markdown_content)
    return markdown_content

async def visit_webpage_impl(url: str, max_output_length: int = 50000) -> Dict[str, Any]:
    """(异步接口) 供 Tool 调用的核心逻辑，包含安全截断"""
    try:
        # 提前检查依赖，防止在网络请求后才报错
        import markdownify  
    except ImportError:
        return {"content": [{"type": "text", "text": "Error: You must install `markdownify` (pip install markdownify)."}]}

    import requests
    try:
        # 将高 CPU 开销的解析和高 I/O 开销的请求放入线程池
        markdown_content = await asyncio.to_thread(_visit_webpage_sync, url)

        # 长度安全截断，保护上下文窗口
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
    """(同步函数) 调用 arXiv API 并解析 XML 获取 PDF 链接"""
    import requests
    import xml.etree.ElementTree as ET
    
    # 构造请求，arXiv API 不需要 API Key
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
    
    # 解析 Atom XML 格式
    root = ET.fromstring(response.text)
    
    # 定义 XML 命名空间
    ns = {'atom': 'http://www.w3.org/2005/Atom'}
    
    papers = []
    for entry in root.findall('atom:entry', ns):
        title = entry.find('atom:title', ns).text.replace('\n', ' ').strip()
        summary = entry.find('atom:summary', ns).text.replace('\n', ' ').strip()
        
        # 提取网页版链接和 PDF 链接
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
    """(异步接口) 供 Tool 调用的核心逻辑"""
    try:
        # 将网络请求和 XML 解析推入后台线程
        papers = await asyncio.to_thread(_arxiv_search_sync, query, max_results)
        
        if not papers:
            return {"content": [{"type": "text", "text": f"No open-access papers found for query: '{query}'"}]}
            
        # 格式化输出，专门凸显 PDF 链接供 Agent 识别
        snippets = []
        for idx, paper in enumerate(papers):
            pdf_url = paper["pdf_link"] + ".pdf" if paper["pdf_link"] else "No PDF available"
            snippets.append(
                f"### {idx + 1}. {paper['title']}\n"
                f"**PDF Download Link**: {pdf_url}\n"
                f"**Abstract**: {paper['summary'][:500]}...\n" # 截断摘要以节省 token
            )
            
        final_text = "## Academic Search Results (Open Access)\n\n" + "\n\n".join(snippets)
        return {"content": [{"type": "text", "text": final_text}]}
        
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error searching academic papers: {str(e)}"}]}