from typing import Literal

_CODE_EXTENSIONS: frozenset[str] = frozenset({
    ".py", ".js", ".jsx", ".ts", ".tsx",
    ".cs", ".java", ".go", ".rs", ".rb",
    ".php", ".cpp", ".c", ".h", ".hpp",
    ".sql", ".sh", ".bash", ".zsh",
    ".swift", ".kt", ".scala", ".r", ".m",
})


def categorize(filename: str, content_type: str) -> Literal["document", "code"]:
    if "." in filename:
        ext = "." + filename.rsplit(".", 1)[-1].lower()
        if ext in _CODE_EXTENSIONS:
            return "code"
    if "text/x-" in content_type or "application/x-" in content_type:
        return "code"
    return "document"
