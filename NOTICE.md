# Third-party content

## tldr-pages

`tldr.json.gz` contains command descriptions and examples from
[tldr-pages](https://github.com/tldr-pages/tldr), copyright © 2014—present
the [tldr-pages team](https://github.com/orgs/tldr-pages/people) and
[contributors](https://github.com/tldr-pages/tldr/graphs/contributors),
licensed under the
[Creative Commons Attribution 4.0 International License](https://creativecommons.org/licenses/by/4.0/)
(CC BY 4.0).

Changes made: `scripts/build_tldr.py` takes the English pages for the
common, linux and osx platforms from release v2.3, joins each page's
description into one line, removes the "More information" links, and
stores the examples as description and command pairs. When Clishe shows
the examples it removes tldr's option-letter markers (`E[x]tract` becomes
`Extract`) and writes placeholders as `<path/to/file>` instead of
`{{path/to/file}}`; when it offers an example to run, placeholders become
Clishe's own (`<file>`).

## Thinking orbs

`orbs.py` ports the orb geometry of
[thinking-orbs](https://www.npmjs.com/package/thinking-orbs) 0.3.2 by
Jakub Antalik from JavaScript to Python, and draws it with braille
characters in the terminal instead of on a canvas.

```text
MIT License

Copyright (c) 2026 Jakub Antalik

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

The rest of Clishe is MIT-licensed (see LICENSE).
