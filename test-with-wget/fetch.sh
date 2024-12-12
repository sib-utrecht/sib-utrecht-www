#!/run/current-system/sw/bin/bash

# Based on
# https://superuser.com/questions/1415717/how-to-download-an-entire-site-with-wget-including-its-images
wget \
     --user='dev' \
     --password='ictcie' \
     --recursive \
     --level 30 \
     --no-clobber \
     --page-requisites \
     --adjust-extension \
     --content-on-error \
     --span-hosts \
     --convert-links \
     -N \
     --domains dev2.sib-utrecht.nl \
     --no-parent \
        dev2.sib-utrecht.nl 

# wget \
#      --user='dev' \
#      --password='ictcie' \
#      --recursive \
#      --level 30 \
#      --no-clobber \
#      --page-requisites \
#      --adjust-extension \
#      --span-hosts \
#      --convert-links \
#      --content-on-error \
#      -N \
#      --domains dev2.sib-utrecht.nl \
#      --no-parent \
#          dev2.sib-utrecht.nl/404