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

The rest of Clishe is MIT-licensed (see LICENSE).
