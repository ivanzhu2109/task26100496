# sensitive_words — 公告发布前的本地敏感词检查库

渲染 `{{customer.field}}` 模板，在与词典相同的归一化规则下查找敏感词，
并把每次命中精确追溯回模板字面量或某一次变量替换的原字符，供编辑器标红。

## 运行测试

```bash
python3 -m pytest tests/ -q
```

## 接口

```python
from sensitive_words import compile_dictionary, inspect

dictionary = compile_dictionary(["bad", "å"])   # 编译一次，多次复用
hits = inspect(dictionary, "b{{customer.x}}d", {"x": "​A"})
```

- `compile_dictionary(words)`：编译敏感词集合，返回 `CompiledDictionary`。
  归一化后为空或重复的词会抛出 `ValueError`。
- `inspect(compiled, template, values)`：渲染模板并返回 `list[Hit]`，
  包含重叠命中。`values` 以字段名（不含 `customer.` 前缀）为键；
  未提供的字段按空字符串处理，替换值不再递归解释为模板。

### Hit

- `word`：命中的词典原词。
- `start` / `end`：命中在**归一化后正文**中的码点区间 `[start, end)`。
- `sources`：实际贡献该命中的全部原字符来源（不含无关字符），两种类型：
  - `LiteralSource(position)`：模板字面量字符，`position` 为模板中的码点下标。
  - `VariableSource(placeholder_start, field, value_index)`：变量替换字符，
    分别为占位符在模板中的起始下标、字段名、字符在替换值中的下标。

### 归一化规则

词典与渲染后的完整正文使用相同规则：先删除 U+200B / U+200C / U+200D / U+FEFF，
再执行 Unicode NFKC，最后执行 `str.casefold`。不删除任何空白或标点。
匹配是归一化字符串上的精确连续子串匹配。

### 来源语义

- 分解或大小写展开后的字符继承原字符来源；规范重排不改变来源。
- 多个字符组合（如 `A` + U+030A → `Å`）时，来源取参与字符来源的并集，
  组合允许跨模板字面量与变量替换边界发生。
- 被删除的零宽字符没有贡献，不会出现在任何 `sources` 中。
- 一次原字符展开后可以参与多个不同位置的命中。
