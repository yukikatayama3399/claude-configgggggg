"""prompts/*.txt を template.html に差し込んで page.html（共有ページの原稿）を作る。

プロンプトの正本は prompts/ のテキスト。直したらこれを回して page.html を作り直し、
Artifact に同じパスで publish し直す。
"""
import html
import pathlib
import re

here = pathlib.Path(__file__).parent
page = (here / "template.html").read_text(encoding="utf-8")


def prompt(m: re.Match) -> str:
    key = m.group(1)
    [path] = here.glob(f"prompts/{key}_*.txt")
    return html.escape(path.read_text(encoding="utf-8").rstrip("\n"), quote=False)


page, n = re.subn(r"<!--PROMPT:(\d+)-->", prompt, page)
(here / "page.html").write_text(page, encoding="utf-8")
print(f"page.html: {n} prompts, {len(page):,} chars")
