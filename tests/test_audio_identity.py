#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Compile the actual HP/ASUS identity selector with mocked DMI queries."""
from pathlib import Path
import subprocess
import tempfile
import unittest

root = Path(__file__).resolve().parents[1]
patch = (root / "02-drivers/soundwire/hp-audio-identity.patch").read_text()
source = "\n".join(line[1:] for line in patch.splitlines()
                   if line.startswith("+") and not line.startswith("+++"))
start = source.index("static void mt8901_set_oem_ssid(")
end = source.index("\n}\n", start) + 3
function = source[start:end]
prefix = r'''
#include <assert.h>
#include <stdbool.h>
#include <string.h>
#include <stdio.h>
enum {DMI_SYS_VENDOR,DMI_PRODUCT_NAME,DMI_BOARD_VENDOR,DMI_BOARD_NAME,DMI_BIOS_VERSION};
static const char *identity[5];
struct snd_soc_card {unsigned int vendor,device,calls;};
static bool dmi_match(int k,const char *s) {return !strcmp(identity[k],s);}
static void snd_soc_card_set_pci_ssid(struct snd_soc_card *c,unsigned int v,unsigned int d)
{c->vendor=v;c->device=d;c->calls++;}
'''
main = r'''
int main(void) {
 const char *hp[]={"HP","HP OmniBook X Laptop 14-ks000","HP","8F22","F.05"};
 const char *asus[]={"ASUS","ProArt P16 H7607BA","ASUSTeK COMPUTER INC.","H7607BA","other"};
 struct snd_soc_card c={0};
 memcpy(identity,hp,sizeof(identity));mt8901_set_oem_ssid(&c);
 assert(c.calls==1 && c.vendor==0x103c && c.device==0x8f22);
 for (unsigned int k=0;k<5;k++) {
  memcpy(identity,hp,sizeof(identity));identity[k]="other";
  c=(struct snd_soc_card){0};mt8901_set_oem_ssid(&c);assert(!c.calls);
 }
 memcpy(identity,asus,sizeof(identity));c=(struct snd_soc_card){0};
 mt8901_set_oem_ssid(&c);assert(c.calls==1 && c.vendor==0x1043 && c.device==0x1484);
 for (unsigned int k=0;k<4;k++) {
  memcpy(identity,asus,sizeof(identity));identity[k]="other";
  c=(struct snd_soc_card){0};mt8901_set_oem_ssid(&c);assert(!c.calls);
 }
 puts("Production identity selector passed: exact HP/F.05, mismatched fields, unchanged ASUS, other boards.");
 return 0;
}
'''
class AudioIdentity(unittest.TestCase):
    def test_hp_exact_match_and_asus_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/"test.c";binary=Path(d)/"test"
            file.write_text(prefix+function+main)
            subprocess.run(["gcc","-Wall","-Wextra","-Werror","-fsanitize=address,undefined",
                            str(file),"-o",str(binary)],check=True)
            subprocess.run([str(binary)],check=True)

if __name__ == "__main__":
    unittest.main()
