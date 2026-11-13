// SPDX-License-Identifier: GPL-2.0-only
/*
 * HP OmniBook X 14-ks000 / 8F22 / F.05 suspend candidate.
 *
 * Supply the Microsoft LPS0 notifications missing from this arm64 kernel.
 * Protocol: NVIDIA's power_wrap LPS0 patch (Kaushal Rajeev Butala), carried in
 * omacom/omarchy-pkgs 1111; late/early timing follows PR 1958 patch 1123.
 * NVMe link-state mask follows Ryan Hughes' N1x quirk, patch 1024.
 * See docs/sleep.md for pinned source URLs and remaining hardware validation.
 *
 * This companion uses exported APIs, not private power_wrap/ACPI structures.
 * Loading it only queries firmware and enables supported NVMe link states.
 * LPS0 methods run only during explicit s2idle/PSCI system-suspend transitions.
 */
#include <linux/acpi.h>
#include <linux/delay.h>
#include <linux/dmi.h>
#include <linux/module.h>
#include <linux/pci.h>
#include <linux/platform_device.h>
#include <linux/suspend.h>
#include <generated/utsrelease.h>

#include "lps0_sequence.h"

#define HP_SLEEP_NAME "hp-n1x-sleep"
#define HP_NVME_STATES (PCIE_LINK_STATE_L1 | PCIE_LINK_STATE_L1_1_PCIPM | \
			PCIE_LINK_STATE_L1_2_PCIPM)

static const guid_t lps0_guid = GUID_INIT(0x11e00d56, 0xce64, 0x47ce,
					0x83, 0x7b, 0x1f, 0x89, 0x8f, 0x9a, 0xa4, 0x61);

static struct acpi_device *pep;
static struct platform_device *companion;
static struct device *pep_device;
static struct pci_dev *nvme;
static bool nvme_changed;
static bool probed;
static bool deep_cycle;

static int hp_notify(void *unused, unsigned int function)
{
	union acpi_object *result;

	result = acpi_evaluate_dsm(pep->handle, &lps0_guid, 0, function, NULL);
	if (!result) {
		pr_err(HP_SLEEP_NAME ": LPS0 function %u failed\n", function);
		return -EIO;
	}
	ACPI_FREE(result);
	pr_info(HP_SLEEP_NAME ": LPS0 function %u completed\n", function);
	return 0;
}

static struct hp_lps0_sequence sequence = { .notify = hp_notify };

static int hp_suspend_late(struct device *dev)
{
	int ret;

	if (pm_suspend_target_state != PM_SUSPEND_TO_IDLE)
		return 0;
	ret = hp_lps0_enter(&sequence);
	if (ret) {
		dev_err(dev, "firmware prepare failed; aborting suspend (pending %#x)\n",
			sequence.pending);
		return ret;
	}
	/* Let the EC event run while device IRQ handlers are still available. */
	msleep(3000);
	dev_info(dev, "LPS0 entry complete; EC settling delay finished\n");
	return 0;
}

static int hp_resume_early(struct device *dev)
{
	int ret = hp_lps0_restore(&sequence);

	if (ret)
		dev_err(dev, "firmware restore failed; pending exits %#x\n", sequence.pending);
	else
		dev_info(dev, "LPS0 restore complete\n");
	return ret;
}

/* NVIDIA's upstream MT8901 fix also arms EC wake around PSCI SYSTEM_SUSPEND. */
static int hp_suspend_noirq(struct device *dev)
{
	int ret;

	if (pm_suspend_target_state != PM_SUSPEND_MEM)
		return 0;
	deep_cycle = true;
	ret = hp_lps0_enter(&sequence);
	if (ret)
		dev_err(dev, "PSCI sleep notification failed; aborting suspend\n");
	else
		dev_info(dev, "LPS0 entry complete for PSCI system suspend\n");
	return ret;
}

static int hp_resume_noirq(struct device *dev)
{
	int ret;

	if (!deep_cycle)
		return 0;
	ret = hp_lps0_restore(&sequence);
	if (ret)
		dev_err(dev, "PSCI wake notifications failed; retrying at resume_early\n");
	return ret;
}

static void hp_complete(struct device *dev)
{
	if (hp_lps0_restore(&sequence))
		dev_err(dev, "firmware exit retry failed; pending exits %#x\n", sequence.pending);
	deep_cycle = false;
}

static const struct dev_pm_ops hp_pm_ops = {
	.suspend_late = hp_suspend_late,
	.resume_early = hp_resume_early,
	.suspend_noirq = hp_suspend_noirq,
	.resume_noirq = hp_resume_noirq,
	.complete = hp_complete,
};

static int hp_probe(struct platform_device *pdev)
{
	probed = true;
	dev_info(&pdev->dev, "HP F.05 candidate ready; LPS0 functions 0x3f8; s2idle/PSCI suspend\n");
	return 0;
}

static struct platform_driver hp_driver = {
	.probe = hp_probe,
	.driver = {
		.name = HP_SLEEP_NAME,
		.pm = &hp_pm_ops,
		.suppress_bind_attrs = true,
	},
};

static int hp_nvme_enable(void)
{
	struct pci_dev *bridge;
	int cap, ret;
	u16 control;
	u32 substates;

	nvme = pci_get_device(0x1e81, 0x6d14, NULL);
	if (!nvme)
		return -ENODEV;
	bridge = pci_upstream_bridge(nvme);
	if (!bridge || bridge->vendor != PCI_VENDOR_ID_NVIDIA || bridge->device != 0x22ce)
		return -ENODEV;
	if (nvme->current_state != PCI_D0 || bridge->current_state != PCI_D0)
		return -EBUSY;
	cap = pci_find_ext_capability(nvme, PCI_EXT_CAP_ID_L1SS);
	if (!cap)
		return -ENODEV;
	ret = pci_read_config_dword(nvme, cap + PCI_L1SS_CAP, &substates);
	if (ret || !(substates & PCI_L1SS_CAP_PCIPM_L1_2))
		return -EOPNOTSUPP;
	ret = pcie_capability_read_word(nvme, PCI_EXP_LNKCTL, &control);
	if (ret)
		return -EIO;
	ret = pci_read_config_dword(nvme, cap + PCI_L1SS_CTL1, &substates);
	if (ret)
		return -EIO;
	/* Refuse to modify an unexpected, already-configured link policy. */
	if ((control & (PCI_EXP_LNKCTL_ASPMC | PCI_EXP_LNKCTL_CLKREQ_EN)) ||
	    (substates & PCI_L1SS_CTL1_L1SS_MASK))
		return -EBUSY;
	cap = pci_find_ext_capability(bridge, PCI_EXT_CAP_ID_L1SS);
	if (!cap || pcie_capability_read_word(bridge, PCI_EXP_LNKCTL, &control) ||
	    pci_read_config_dword(bridge, cap + PCI_L1SS_CTL1, &substates))
		return -EIO;
	if ((control & (PCI_EXP_LNKCTL_ASPMC | PCI_EXP_LNKCTL_CLKREQ_EN)) ||
	    (substates & PCI_L1SS_CTL1_L1SS_MASK))
		return -EBUSY;
	ret = pci_enable_link_state(nvme, HP_NVME_STATES);
	if (ret)
		return ret;
	nvme_changed = true;
	pci_info(nvme, "HP suspend candidate: allowing supported L1 / PCI-PM L1.2\n");
	return 0;
}

static void hp_nvme_restore(void)
{
	if (nvme_changed) {
		/* Restore the checked all-off default without setting a disable mask. */
		if (pci_enable_link_state(nvme, 0))
			pr_err(HP_SLEEP_NAME ": NVMe link rollback failed; reboot to restore firmware policy\n");
		nvme_changed = false;
	}
	pci_dev_put(nvme);
	nvme = NULL;
}

static int __init hp_sleep_init(void)
{
	unsigned long long plid;
	int ret;

	if (!dmi_match(DMI_BOARD_NAME, "8F22") ||
	    !dmi_match(DMI_PRODUCT_NAME, "HP OmniBook X Laptop 14-ks000") ||
	    !dmi_match(DMI_BIOS_VERSION, "F.05") ||
	    strcmp(UTS_RELEASE, "7.0.0-1022-nvidia"))
		return -ENODEV;
	pep = acpi_dev_get_first_match_dev("NVDA6210", NULL, -1);
	if (!pep)
		return -ENODEV;
	if (ACPI_FAILURE(acpi_evaluate_integer(pep->handle, "PLID", NULL, &plid)) ||
	    plid != 2 || !acpi_check_dsm(pep->handle, &lps0_guid, 0, 0x3f8)) {
		ret = -EOPNOTSUPP;
		goto put_pep;
	}
	pep_device = get_device(acpi_get_first_physical_node(pep));
	if (!pep_device) {
		ret = -ENODEV;
		goto put_pep;
	}
	ret = hp_nvme_enable();
	if (ret)
		goto restore_link;
	ret = platform_driver_register(&hp_driver);
	if (ret)
		goto restore_link;
	companion = platform_device_alloc(HP_SLEEP_NAME, PLATFORM_DEVID_NONE);
	if (!companion) {
		ret = -ENOMEM;
		goto unregister_driver;
	}
	/* Order this companion before PEP during sleep and after it on resume. */
	companion->dev.parent = pep_device;
	ret = platform_device_add(companion);
	if (ret) {
		platform_device_put(companion);
		goto unregister_driver;
	}
	if (!probed) {
		ret = -ENODEV;
		platform_device_unregister(companion);
		goto unregister_driver;
	}
	return 0;

unregister_driver:
	platform_driver_unregister(&hp_driver);
restore_link:
	hp_nvme_restore();
	put_device(pep_device);
put_pep:
	acpi_dev_put(pep);
	return ret;
}

static void __exit hp_sleep_exit(void)
{
	if (hp_lps0_restore(&sequence))
		pr_err(HP_SLEEP_NAME ": firmware exit remains pending\n");
	platform_device_unregister(companion);
	platform_driver_unregister(&hp_driver);
	hp_nvme_restore();
	put_device(pep_device);
	acpi_dev_put(pep);
}

module_init(hp_sleep_init);
module_exit(hp_sleep_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("HP OmniBook X N1X F.05 LPS0 and NVMe sleep candidate");
MODULE_VERSION("0.2");
