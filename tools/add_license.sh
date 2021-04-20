#!/bin/sh

JS_LICENSE=$(cat <<EOF
// Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
// All rights reserved.
EOF)

PY_LICENSE=$(cat <<EOF
# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
EOF)

for file in $*; do
    extension=`echo $file | awk -F . '{print $NF}'`
    if [ "$extension" == "py" ]; then
        LICENSE=$PY_LICENSE
    elif [ "$extension" == "js" ]; then
        LICENSE=$JS_LICENSE
    else
        echo "Unknown file extension, skipping. $file"
        continue
    fi

    # Check to make sure the license is not already in the file.
    if [ "`head -10 $file | grep "$LICENSE"`" == "" ]; then
        # Use ed to insert the license at the top of the file.
        (echo '0a'; echo "$LICENSE"; echo '.'; echo 'wq') | ed -s $file
    fi
done
