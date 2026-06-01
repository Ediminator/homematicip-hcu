#!/bin/bash

pref_HM="HM"
pref_HmIP="HmIP"
pref_HmIPW="HmIPW"
pref_ELV="ELV"

rm -f run_*
rm -f *.tar.gz
rm -f *.tgz
runfile="run_log.txt"
touch ${runfile}

#ip=$(curl -s https://api.ipify.org)
#echo "External IP: $ip" | tee -a ${runfile}

echo "Getting firmware list" | tee -a ${runfile}
output=`curl -s 'https://update.homematic.com/firmware/api/firmware/search/DEVICE' | sed s/'homematic.com.setDeviceFirmwareVersions('/''/ | sed s/');'/''/ |  jq -r '.[] | "\(.type)"'|sort -u`
cnt=$(wc -w <<< "$output"|xargs)
i=0
for row in ${output}; do
  i=$((i+1))
  echo -n -e "Downloading firmware file $i of $cnt (${row})              \r" | tee -a ${runfile}
  printf "\n" >> ${runfile}
  curl -fsSLOJ  "https://ccu3-update.homematic.com/firmware/download?cmd=download&serial=0&product=${row}"
done
echo "" | tee -a ${runfile}
echo "Moving files into directories" | tee -a ${runfile}
for f in *gz; do
  pref=$(ls $f|awk -F'[-_]' {'print $1'})
  
  case $pref in
    ([Hh][Mm])             pref=$pref_HM;;
    ([Hh][Mm][Ii][Pp])     pref=$pref_HmIP;;
    ([Hh][Mm][Ii][Pp][Ww]) pref=$pref_HmIPW;;
    ([Ee][Ll][Vv])         pref=$pref_ELV;;
  esac

  [ ! -d $pref ] && mkdir $pref
  mv $f $pref/
done

echo "Regen archive list" | tee -a ${runfile}
for f in {$pref_HM,$pref_HmIP,$pref_HmIPW,$pref_ELV}/*gz; do

  echo ${f}

  pref=$(dirname ${f})
  
  #parse info file
  tar -xf "${f}" info 2>/dev/null
  if [ ! -f "info" ]; then
    echo "WARNING: ${f} has no info file" | tee -a ${runfile}
  else
    fwversion=`grep "FirmwareVersion=" info|cut -d "=" -f 2`
    fwversion=${fwversion//[$'\n\r']/}
    fwdevicename=`grep "Name=" info|cut -d "=" -f 2`
    fwdevicename=${fwdevicename//[$'\n\r']/}
    # fix uppercase HMIP-xxxxx
    fwdevicename="${pref}-$(echo ${fwdevicename} | cut -d '-' -f2-)"
    fwccu2minversion=$(grep "CCUFirmwareVersionMin=" info | cut -d "=" -f 2)
    fwccu2minversion=${fwccu2minversion//[$'\n\r']/}
    fwccu3minversion=$(grep "CCU3FirmwareVersionMin=" info 2>/dev/null | cut -d "=" -f 2)
    fwccu3minversion=${fwccu3minversion//[$'\n\r']/}

    # fix/patch minimum ccu2/ccu3 version infos
    if [ "${fwccu2minversion}" == "3.0.0" ]; then
      fwccu2minversion=""
    fi
    if [ -z "${fwccu3minversion}" ] || [[ ! ${fwccu3minversion} =~ ^3\. ]]; then

      # patch info file as there should always be a minimum CCU3 version
      if [ -z "${fwccu3minversion}" ]; then
        echo "WARNING: ${f} - Missing 'CCU3FirmwareVersionMin' in info. Fixing!" | tee -a ${runfile}
      else
        echo "WARNING: ${f} - CCU3FirmwareVersionMin != 3.x.x (${fwccu3minversion}). Fixing!" | tee -a ${runfile}
      fi

      fwccu3minversion="3.0.0"

      # redo the archive and make sure the info file contains
      # CCU3FirmwareVersionMin under all circumstances
      TMPDIR=$(mktemp -d)
      tar -C ${TMPDIR} -xf "${f}"
      cp -a "${TMPDIR}/info" "${TMPDIR}/info.bak"
      sed -i '
        # if line exists, replace and set flag
        /^CCU3FirmwareVersionMin=/{
          s/.*/CCU3FirmwareVersionMin=3.0.0/
          x; s/.*/1/; x
        }
        # at the end: if no flag add line
        ${
          x
          /1/! a\CCU3FirmwareVersionMin=3.0.0
          x
        }
      ' ${TMPDIR}/info
      touch -r "${TMPDIR}/info.bak" "${TMPDIR}/info"
      rm -f "${TMPDIR}/info.bak"
      rm -f "${f}"
      DSTDIR=$(pwd)
      (cd ${TMPDIR} && tar --numeric-owner --owner=0 --group=0 -czf "${DSTDIR}/${f}" *)
      rm -rf ${TMPDIR}
    fi
    rm -f info
  fi

  # parse changelog
  SHA256SUM=$(sha256sum ${f} | cut -d' ' -f1)
  fb=$(basename ${f})
  echo "## [${fb}](https://raw.githubusercontent.com/OpenCCU/HMDeviceFirmware/master/${pref}/${fb})" >./docs/changelogs/changelog_${fb%%.*}.md
  echo -n "Required CCU firmware version: &#8805; ${fwccu3minversion}" >>./docs/changelogs/changelog_${fb%%.*}.md
  if [ -n "${fwccu2minversion}" ]; then
    echo -n " / ${fwccu2minversion}" >>./docs/changelogs/changelog_${fb%%.*}.md
  fi
  echo "<br/>" >>./docs/changelogs/changelog_${fb%%.*}.md
  echo "<sub>sha256: ${SHA256SUM}</sub>" >>./docs/changelogs/changelog_${fb%%.*}.md
  echo "" >>./docs/changelogs/changelog_${fb%%.*}.md
  tar -zxf "${f}" changelog.txt 2>/dev/null
  if [ ! -f "changelog.txt" ]; then
    echo "WARNING: ${f} has no changelog.txt" | tee -a ${runfile}
    echo "C H A N G E L O G" >>./docs/changelogs/changelog_${fb%%.*}.md
    echo "-----------------" >>./docs/changelogs/changelog_${fb%%.*}.md
    echo "" >>./docs/changelogs/changelog_${fb%%.*}.md
    echo "No entries" >>./docs/changelogs/changelog_${fb%%.*}.md
  else
    iconv -f ISO-8859-1 -t UTF-8 changelog.txt >>./docs/changelogs/changelog_${fb%%.*}.md
    rm -f changelog.txt
  fi
  echo -n "| ${fwdevicename} | [V${fwversion}](changelogs/changelog_${fb%%.*}.md) | ${fwccu3minversion} " >> ./docs/_index.md.tmp.$pref
  if [ -n "${fwccu2minversion}" ]; then
    echo -n "/ ${fwccu2minversion} " >> ./docs/_index.md.tmp.$pref
  fi
  echo "| [${fb}](https://raw.githubusercontent.com/OpenCCU/HMDeviceFirmware/master/${pref}/${fb}) | \`${SHA256SUM}\` |" >> ./docs/_index.md.tmp.$pref
  
done

#Build final index.md file
generation_time=$(date --utc +'%d.%m.%Y, %H:%M:%S UTC')
echo "## HomeMatic / Homematic IP Device Firmware Archive"    > ./docs/index.md
echo ""                                          >> ./docs/index.md
echo "_last generated: ${generation_time}_ ([GitHub](https://github.com/OpenCCU/HMDeviceFirmware))"      >> ./docs/index.md
echo ""                                          >> ./docs/index.md
declare -a pref_arr=($pref_HmIP $pref_HmIPW $pref_ELV $pref_HM)
for i in "${pref_arr[@]}"
do
  echo "<details open><summary>$i</summary>"     >> ./docs/index.md
  echo ""                                        >> ./docs/index.md
  echo "| Device Model | Version | &#8805;CCU-FW | Download | SHA256 |"              >> ./docs/index.md
  echo "| ------------- |:-------------:| ------------- | ------------- | ------------- |"       >> ./docs/index.md
  cat ./docs/_index.md.tmp.$i | sort             >> ./docs/index.md
  echo "</details>"                              >> ./docs/index.md
done

rm ./docs/_index.md.*
echo "Done." | tee -a ${runfile}
