#!/bin/bash

pref_HmIP="HmIP"
pref_HmIPW="HmIPW"
pref_ELV="ELV"

runfile="run_log.txt"
: > "${runfile}"

mkdir -p .docs/changelogs

echo "Getting firmware list" | tee -a "${runfile}"
output=$(curl -s 'https://update.homematic.com/firmware/api/firmware/search/DEVICE' \
  | sed 's/homematic\.com\.setDeviceFirmwareVersions(//;s/);//' \
  | jq -r '.[] | .type' \
  | sort -u)

if [ -z "$output" ]; then
  echo "ERROR: No firmware list received" | tee -a "${runfile}"
  exit 1
fi

cnt=$(echo "$output" | grep -c .)
i=0

while IFS= read -r row; do
  i=$((i+1))
  echo "Processing $i/$cnt: ${row}" | tee -a "${runfile}"

  case "${row%%[-_]*}" in
    [Hh][Mm][Ii][Pp][Ww]) pref=$pref_HmIPW ;;
    [Hh][Mm][Ii][Pp])     pref=$pref_HmIP ;;
    [Ee][Ll][Vv])         pref=$pref_ELV ;;
    *)                    pref="${row%%[-_]*}" ;;
  esac

  work_dir=$(mktemp -d)

  if ! curl -fsSLJ --output-dir "${work_dir}" -O \
    "https://ccu3-update.homematic.com/firmware/download?cmd=download&serial=0&product=${row}" 2>>"${runfile}"; then
    echo "WARNING: Failed to download ${row}" | tee -a "${runfile}"
    rm -rf "${work_dir}"
    continue
  fi

  archive=$(ls "${work_dir}"/*gz 2>/dev/null | head -1)
  if [ -z "${archive}" ]; then
    echo "WARNING: No archive found for ${row}" | tee -a "${runfile}"
    rm -rf "${work_dir}"
    continue
  fi

  fb=$(basename "${archive}")
  SHA256SUM=$(sha256sum "${archive}" | cut -d' ' -f1)

  tar -C "${work_dir}" -xf "${archive}" info changelog.txt 2>/dev/null
  rm -f "${archive}"

  fwversion=""
  fwdevicename=""
  fwccu2minversion=""
  fwccu3minversion=""

  if [ ! -f "${work_dir}/info" ]; then
    echo "WARNING: ${fb} has no info file" | tee -a "${runfile}"
  else
    fwversion=$(grep "FirmwareVersion=" "${work_dir}/info" | cut -d "=" -f 2 | tr -d $'\n\r')
    fwdevicename=$(grep "Name=" "${work_dir}/info" | cut -d "=" -f 2 | tr -d $'\n\r')
    fwdevicename="${pref}-$(echo "${fwdevicename}" | cut -d '-' -f2-)"
    fwccu2minversion=$(grep "CCUFirmwareVersionMin=" "${work_dir}/info" | cut -d "=" -f 2 | tr -d $'\n\r')
    fwccu3minversion=$(grep "CCU3FirmwareVersionMin=" "${work_dir}/info" | cut -d "=" -f 2 | tr -d $'\n\r')

    if [ "${fwccu2minversion}" = "3.0.0" ]; then
      fwccu2minversion=""
    fi
    if [ -z "${fwccu3minversion}" ] || [[ ! ${fwccu3minversion} =~ ^3\. ]]; then
      if [ -z "${fwccu3minversion}" ]; then
        echo "WARNING: ${fb} - Missing CCU3FirmwareVersionMin. Using 3.0.0" | tee -a "${runfile}"
      else
        echo "WARNING: ${fb} - CCU3FirmwareVersionMin=${fwccu3minversion} != 3.x.x. Using 3.0.0" | tee -a "${runfile}"
      fi
      fwccu3minversion="3.0.0"
    fi
  fi

  {
    echo "## [${fb}](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/${pref}/${fb})"
    echo -n "Required CCU firmware version: &#8805; ${fwccu3minversion}"
    [ -n "${fwccu2minversion}" ] && echo -n " / ${fwccu2minversion}"
    echo "<br/>"
    echo "<sub>sha256: ${SHA256SUM}</sub>"
    echo ""
  } > "./.docs/changelogs/changelog_${fb%%.*}.md"

  if [ -f "${work_dir}/changelog.txt" ]; then
    iconv -f ISO-8859-1 -t UTF-8 "${work_dir}/changelog.txt" \
      | sed '/^Please note:/,/^Version /{/^Version /!d}' \
      >> "./.docs/changelogs/changelog_${fb%%.*}.md"
  else
    echo "WARNING: ${fb} has no changelog.txt" | tee -a "${runfile}"
    printf "C H A N G E L O G\n-----------------\n\nNo entries\n" >> "./.docs/changelogs/changelog_${fb%%.*}.md"
  fi

  {
    echo -n "| ${fwdevicename} | [V${fwversion}](changelogs/changelog_${fb%%.*}.md) | ${fwccu3minversion} "
    [ -n "${fwccu2minversion}" ] && echo -n "/ ${fwccu2minversion} "
    echo "| [${fb}](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/${pref}/${fb}) | \`${SHA256SUM}\` |"
  } >> "./.docs/_index.md.tmp.${pref}"

  rm -rf "${work_dir}"
done <<< "$output"

generation_time=$(date --utc +'%d.%m.%Y, %H:%M:%S UTC')
{
  echo "## HomeMatic / Homematic IP Device Firmware Archive"
  echo ""
  echo "_last generated: ${generation_time}_ ([GitHub](https://github.com/ediminator/homematicip-hcu))"
  echo ""
} > ./.docs/index.md

for pref in "$pref_HmIP" "$pref_HmIPW" "$pref_ELV"; do
  {
    echo "<details open><summary>${pref}</summary>"
    echo ""
    echo "| Device Model | Version | &#8805;CCU-FW | Download | SHA256 |"
    echo "| ------------- |:-------------:| ------------- | ------------- | ------------- |"
  } >> ./.docs/index.md
  if [ -f "./.docs/_index.md.tmp.${pref}" ]; then
    sort "./.docs/_index.md.tmp.${pref}" >> ./.docs/index.md
    rm -f "./.docs/_index.md.tmp.${pref}"
  fi
  echo "</details>" >> ./.docs/index.md
done

rm -f ./.docs/_index.md.tmp.*
echo "Done." | tee -a "${runfile}"
