"""ResultMessage 成功/失败语义：SDK 的 is_error 与 subtype 可能不一致，需联合判断。"""


def result_message_indicates_failure(msg: object) -> bool:
    """
    若 is_error 为 True，或 subtype 表明失败（如 error_during_execution），则视为失败。

    对明显否定语义的 subtype（如含 no_error）不做误判。
    """
    if getattr(msg, "is_error", False):
        return True
    st = (getattr(msg, "subtype", None) or "").lower()
    if not st:
        return False
    if "no_error" in st or "non_error" in st:
        return False
    return any(k in st for k in ("error", "fail", "abort"))
