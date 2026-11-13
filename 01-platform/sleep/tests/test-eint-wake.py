#!/usr/bin/python3
# SPDX-License-Identifier: MIT
"""Exercise the patched production wake helpers with mocked MMIO/IRQ data."""
from pathlib import Path
import re
import subprocess
import tempfile

import sys
root=Path(sys.argv[1]).resolve()
source=(root/'drivers/pinctrl/mediatek/mtk-eint.c').read_text()
def function(name):
    match=re.search(r'(?:static )?(?:void|bool|int) '+name+r'\([^;]*?\n\{',source,re.S)
    assert match,name
    end=match.end();depth=1
    while depth:
        depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[match.start():end]

prefix=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include <stdio.h>
typedef uint32_t u32;
#define __iomem
#define BIT(n) (1U<<(n))
#define DIV_ROUND_UP(n,d) (((n)+(d)-1)/(d))
#define __ffs(n) __builtin_ctz(n)
struct mtk_eint_hw {unsigned int ap_num;bool has_event_mask;};
struct mtk_eint_regs {unsigned int event_set,event_clr;};
struct mtk_eint_pin {unsigned int index,instance;};
struct mtk_eint {
 struct mtk_eint_hw *hw;struct mtk_eint_regs *regs;
 struct mtk_eint_pin pins[128];int nbase;uint16_t base_pin_num[2];
 unsigned int *event_pins,num_event_pins;
 unsigned int wake_mask[2][3],cur_mask[2][3],pin_list[2][128];
};
struct irq_data {unsigned int hwirq;struct mtk_eint *owner;};
struct write {unsigned int pin,offset,value;};
static struct write writes[64],pending;
static unsigned int count,chip_restores;
static struct mtk_eint *irq_data_get_irq_chip_data(struct irq_data *d) {return d->owner;}
static void *mtk_eint_get_offset(struct mtk_eint *e,unsigned int pin,unsigned int offset) {
 assert(pin<e->hw->ap_num);pending=(struct write){.pin=pin,.offset=offset};return &pending;
}
static void writel(unsigned int value,void *reg) {
 assert(reg==&pending && count<64);pending.value=value;writes[count++]=pending;
}
static void mtk_eint_chip_write_mask(struct mtk_eint *e,unsigned int mask[][3]) {
 assert(mask==e->cur_mask);chip_restores++;
}
'''
main=r'''
int main(void) {
 struct mtk_eint_hw hw={.ap_num=101,.has_event_mask=true};
 struct mtk_eint_regs regs={.event_set=0x840,.event_clr=0x880};
 unsigned int static_pins[]={20};
 struct mtk_eint e={.hw=&hw,.regs=&regs,.nbase=2,.base_pin_num={64,37},
                   .event_pins=static_pins,.num_event_pins=1};
 for(unsigned int i=0;i<101;i++) {
   unsigned int inst=i<64?0:1,idx=i<64?i:i-64;
   e.pins[i]=(struct mtk_eint_pin){.index=idx,.instance=inst};
   e.pin_list[inst][idx]=i;
 }
 struct irq_data d={.hwirq=33,.owner=&e};
 assert(mtk_eint_irq_set_wake(&d,1)==0 && e.wake_mask[0][1]==BIT(1));
 assert(count==1 && writes[0].pin==33 && writes[0].offset==0x880 && writes[0].value==BIT(1));
 assert(mtk_eint_irq_set_wake(&d,0)==0 && e.wake_mask[0][1]==0);
 assert(count==2 && writes[1].offset==0x840 && writes[1].value==BIT(1));
 count=0;d.hwirq=20;
 assert(mtk_eint_irq_set_wake(&d,1)==0 && count==1);
 assert(mtk_eint_irq_set_wake(&d,0)==0 && count==1); /* static ACPI event stays unmasked */
 assert(mtk_eint_is_static_event_unmask_pin(&e,20));
 assert(!mtk_eint_is_static_event_unmask_pin(&e,33));
 count=0;e.event_pins=NULL;
 assert(!mtk_eint_is_static_event_unmask_pin(&e,20));
 mtk_eint_apply_event_unmask(&e);assert(count==0);
 e.event_pins=static_pins;
 mtk_eint_write_event_mask(&e,101,0x880);assert(count==0);
 e.pins[33].instance=2;
 mtk_eint_write_event_mask(&e,33,0x880);assert(count==0);
 e.pins[33].instance=0;
 hw.has_event_mask=false;d.hwirq=33;
 assert(mtk_eint_irq_set_wake(&d,1)==0 && e.wake_mask[0][1]==BIT(1));
 mtk_eint_apply_event_unmask(&e);mtk_eint_apply_wake_event_unmask(&e);
 assert(count==0); /* unrelated SoCs never receive event-register writes */
 assert(mtk_eint_irq_set_wake(&d,0)==0 && count==0);
 hw.has_event_mask=true;
 e.wake_mask[0][1]=BIT(1);
 e.wake_mask[1][0]=BIT(9);
 e.wake_mask[1][1]=BIT(4)|BIT(31); /* ignore beyond this bank's 37 valid pins */
 assert(mtk_eint_do_resume(&e)==0 && chip_restores==1 && count==4);
 assert(writes[0].pin==20 && writes[1].pin==33 && writes[2].pin==73 && writes[3].pin==100);
 for(unsigned int i=0;i<count;i++)assert(writes[i].offset==0x880);
 assert(writes[1].value==BIT(1) && writes[2].value==BIT(9) && writes[3].value==BIT(4));
 puts("Production wake helpers passed: enable/disable, static ACPI pin, SoC guard, banks, bounds and resume.");
 return 0;
}
'''
body='\n\n'.join(function(name) for name in [
    'mtk_eint_write_event_mask','mtk_eint_event_unmask_one',
    'mtk_eint_is_static_event_unmask_pin','mtk_eint_event_mask_one',
    'mtk_eint_apply_event_unmask','mtk_eint_apply_wake_event_unmask',
    'mtk_eint_irq_set_wake','mtk_eint_do_resume'])
with tempfile.TemporaryDirectory(prefix='hp-eint-wake-test-') as directory:
    c=Path(directory)/'wake.c';binary=Path(directory)/'wake'
    c.write_text(prefix+body+main)
    # Match the kernel's sign-comparison setting for its mixed IRQ/index types.
    subprocess.run(['gcc','-Wall','-Wextra','-Werror','-Wno-sign-compare','-fsanitize=address,undefined',
                    str(c),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)
