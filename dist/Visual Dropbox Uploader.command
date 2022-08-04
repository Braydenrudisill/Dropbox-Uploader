#!/bin/bash
dir=${0%/*}
if [ -d "$dir" ]; then
  cd "$dir"
fi
./Dropbox-Uploader.app/Dropbox-Uploader
