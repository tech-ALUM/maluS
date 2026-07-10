# Legacy v0 GUI

`rtd.html` is the **maluS v0** single-file GUI: open it in any browser to
load/save an `rtd.yaml` locally, with no server and no network. It enforces the
same closure rule (the owner can never mark a finding *verified*).

It is **retained as legacy**. The v1 interface is the served web application
(`malus serve` → `/ui`), backed by a database. Use this file only for reference
or to inspect an exported `rtd.yaml` offline.

To bring a v0 review into v1:

```sh
malus import path/to/reviews/<review-id>
```
