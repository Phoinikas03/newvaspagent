"""测试 tools.py 中的各项搜索和网页浏览逻辑。

注意：带有 _tool 后缀的函数返回的是 SdkMcpTool 对象，不能直接 await 调用。
这里测试可复用的实现 _impl()，与 MCP 工具内部调用的是同一套逻辑。
"""
import asyncio
from tool import (
    get_poscar_impl,
    duckduckgo_search_impl, 
    google_search_impl, 
    visit_webpage_impl,
    arxiv_search_impl,  
    setup_vasp_inputs_impl,
    semanticscholar_search_impl  # 导入新增的 Semantic Scholar 实现
)


async def test_get_poscar_from_md():
    print("=== 开始测试 get POSCAR from Materials Project ===")
    result = await get_poscar_impl("mp-2815", workspace_dir="/mnt/data_x3/xiazeyu/learn-claude-code/workspace")
    print(result)
    print("=== get POSCAR from Materials Project 测试通过 ===\n")
    return result


async def test_duckduckgo_search():
    print("=== 开始测试 DuckDuckGo Search ===")
    result = await duckduckgo_search_impl("Tsinghua University", max_results=5)

    assert "content" in result
    content = result["content"]
    assert isinstance(content, list) and len(content) > 0
    assert content[0]["type"] == "text"
    text = content[0]["text"]

    print("=== DuckDuckGo 搜索结果 ===")
    print(text)
    print("=== DuckDuckGo Search 测试通过 ===\n")
    return result


async def test_google_search():
    print("=== 开始测试 Google Search ===")
    
    # 提醒：实际请求需要确保环境中配置了 SERPAPI_API_KEY 或 SERPER_API_KEY
    provider = "serper"
    result = await google_search_impl("claude agent sdk", provider=provider)

    assert "content" in result
    content = result["content"]
    assert isinstance(content, list) and len(content) > 0
    assert content[0]["type"] == "text"
    text = content[0]["text"]

    print("=== Google 搜索结果 ===")
    print(text)
    print("=== Google Search 测试通过 ===\n")
    return result


async def test_visit_webpage():
    print("=== 开始测试 Visit Webpage ===")
    
    # 使用维基百科进行测试，同时将 max_output_length 设置得稍微小一点，以测试截断逻辑是否生效
    test_url = "https://github.com/anthropics/claude-agent-sdk-python"
    
    result = await visit_webpage_impl(test_url, max_output_length=20000)

    assert "content" in result
    content = result["content"]
    assert isinstance(content, list) and len(content) > 0
    assert content[0]["type"] == "text"
    text = content[0]["text"]

    print(f"=== {test_url} 抓取结果 ===")
    print(text)
    print("=== Visit Webpage 测试通过 ===\n")
    return result


async def test_arxiv_search():
    print("=== 开始测试 arXiv 学术搜索 ===")
    
    query = 'all:"agent" AND cat:cond-mat.mtrl-sci'
    result = await arxiv_search_impl(query, max_results=3)

    assert "content" in result
    content = result["content"]
    assert isinstance(content, list) and len(content) > 0
    assert content[0]["type"] == "text"
    text = content[0]["text"]

    print(f"=== arXiv 查询 [{query}] 结果 ===")
    print(text)
    print("=== arXiv 学术搜索测试通过 ===\n")
    return result


async def test_setup_vasp_inputs():
    print("=== 开始测试 setup VASP inputs ===")
    result = await setup_vasp_inputs_impl(
        poscar_path="/mnt/data_x3/xiazeyu/learn-claude-code/workspace/POSCAR_mp-2815", 
        incar_path="/mnt/data_x3/xiazeyu/learn-claude-code/workspace/INCAR", 
        workspace_dir="/mnt/data_x3/xiazeyu/learn-claude-code/workspace", 
        kpoints_density=300
    )
    print(result)
    print("=== setup VASP inputs 测试通过 ===\n")
    return result


async def test_semanticscholar_search():
    print("=== 开始测试 Semantic Scholar 学术搜索 ===")
    
    # 构造一个符合 Semantic Scholar 语法的查询词 (测试高级语法 + 操作符)
    # 这里测试检索包含确切短语 "generative ai" 且必须包含 "materials" 关键词的文献
    query = 'Ga2O3 computational material science'
    
    # 设置提取前 3 条结果
    result = await semanticscholar_search_impl(query, max_results=3)

    assert "content" in result
    content = result["content"]
    assert isinstance(content, list) and len(content) > 0
    assert content[0]["type"] == "text"
    text = content[0]["text"]

    print(f"=== Semantic Scholar 查询 [{query}] 结果 ===")
    print(text)
    print("=== Semantic Scholar 学术搜索测试通过 ===\n")
    return result


async def main():
    # 可以通过注释/取消注释来单独测试某个工具
    # await test_google_search()
    # await test_visit_webpage()
    # await test_duckduckgo_search()
    # await test_arxiv_search()
    # await test_setup_vasp_inputs()
    # await test_get_poscar_from_md()
    
    # 运行新增的 Semantic Scholar 测试
    await test_semanticscholar_search()


if __name__ == "__main__":
    asyncio.run(main())