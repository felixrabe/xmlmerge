#!/bin/sh

if which python
then
    export PY=python
else
    export PY=/c/python26/python.exe
fi

rm -f tests/*.xml.diff.html

cmd=( "$PY" convert_newlines.py )
echo "${cmd[@]}"
"${cmd[@]}"

for f in tests/*.in.xml
do
    base=${f%.in.xml}
    cmd=( "$PY" xmlmerge.py -i "$f" -o "$base.out.xml" -r "$base.ref.xml" -d )
    echo "${cmd[@]}"
    "${cmd[@]}"
    echo
done
