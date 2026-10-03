# sensitive-words

公告发布前的本地敏感词检查库。渲染 `{{customer.field}}` 模板后做敏感词匹配，
并把每次命中精确定位回模板字面量或某次变量替换的原字符，供编辑器标红。

## 运行测试

```bash
python3 -m unittest discover -s tests -v
```

## 接口

```python
from sensitive_words import compile_dictionary, inspect

compiled = compile_dictionary(["bad", "å"])      # 编译一次，多次复用
hits = inspect(compiled, "b{{customer.x}}d", {"x": "​A"})
```

- `compile_dictionary(words)`：编译敏感词集合，返回可复用的 `CompiledDictionary`。
- `inspect(compiled, template, values)`：渲染模板并返回全部命中（含重叠命中）的 `Hit` 列表。

模板只支持 `{{customer.field}}` 占位符（`field` 为英文字母、数字、下划线）；
替换值按纯文本处理，不递归解释；`values` 缺少字段时抛出 `KeyError`。

词典与渲染后的正文使用相同归一化：先删除 U+200B/U+200C/U+200D/U+FEFF，
再做 Unicode NFKC，最后 `str.casefold()`；匹配是归一化字符串上的精确连续子串匹配。

## 返回值

每个 `Hit`：

- `start` / `end`：命中在归一化后正文中的码点区间（半开）。
- `word`：命中的归一化敏感词。
- `sources`：贡献该命中的全部原字符区间（已合并相邻码点），不含无关字符：
  - `LiteralSource(start, end)`：模板原文中的码点区间。
  - `VariableSource(placeholder_start, field, start, end)`：占位符在模板中的起点、
    字段名、替换值中的码点区间。同一字段多次出现时按 `placeholder_start` 区分。

所有位置均按 Unicode 码点计数。分解/大小写展开的字符继承原字符来源；
规范重排不改变来源；组合字符取参与字符来源的并集；被删除字符没有来源。
