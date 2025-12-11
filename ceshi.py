import json
import re  # 引入正则表达式库，这是关键

str = "251208-recv4MxVw6EsWP"

def hello(args):
    params = args.params
    # 获取 Start 传入的原始编码，并去除首尾空格
    raw_input = str(params.get('spu_code', '')).strip()
    
    # -----------------------------------------------
    # 1. 核心逻辑：使用正则强力提取 Record ID
    # -----------------------------------------------
    # 逻辑：扫描整个字符串，寻找以 "rec" 开头，后面紧跟字母或数字的片段
    # 不管中间是用 - 分隔，还是空格，还是下划线，都能抓到
    pattern = r"(rec[a-zA-Z0-9]{10,})"
    
    match = re.search(pattern, raw_input)
    
    if match:
        # 找到了！提取出 recXXXX...
        real_id = match.group(1)
    else:
        # 没找到类似格式的，假设用户传的就是纯 ID 或其他格式，原样返回
        real_id = raw_input
    
    # -----------------------------------------------
    # 2. 构造 Filter (用于 search_record 搜索)
    # -----------------------------------------------
    # 搜索时还是用原始的完整字符串去匹配（因为你表格里填的是 251208-rec...）
    filter_obj = {
        "conditions": [
            {
                "field_name": "SPU编码",  # 必须与飞书表格列名一致
                "operator": "is",
                "value": [raw_input]      # 用完整的去搜
            }
        ],
        "conjunction": "and"
    }

    return {
        "filter_json": filter_obj,    # 给 search_record 用 (完整字符串)
        "real_record_id": real_id     # 给 update_record 用 (纯净ID)
    }


def main():
    hello(str)


if __name__ == "__main__":
    main()
