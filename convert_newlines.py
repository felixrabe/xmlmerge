#!/usr/bin/env python

import os

test_dir = "tests"
for fn in sorted(os.listdir(test_dir)):
    full_fn = os.path.join(test_dir, fn)
    s = file(full_fn, "rb").read()
    file(full_fn, "wb").write(s.replace("\r\n", "\n"))
