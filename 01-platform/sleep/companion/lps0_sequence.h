/* SPDX-License-Identifier: GPL-2.0-only */
/* Microsoft LPS0 entry/exit ordering, shared by the module and failure tests. */
#ifndef HP_LPS0_SEQUENCE_H
#define HP_LPS0_SEQUENCE_H

struct hp_lps0_sequence {
	unsigned int pending;
	void *context;
	int (*notify)(void *context, unsigned int function);
};

static int hp_lps0_restore(struct hp_lps0_sequence *sequence)
{
	static const unsigned int exits[] = { 6, 9, 8, 4 };
	unsigned int i;
	int result = 0;

	for (i = 0; i < sizeof(exits) / sizeof(exits[0]); ++i) {
		unsigned int bit = 1U << exits[i];
		int ret;

		if (!(sequence->pending & bit))
			continue;
		ret = sequence->notify(sequence->context, exits[i]);
		if (ret) {
			if (!result)
				result = ret;
		} else {
			sequence->pending &= ~bit;
		}
	}
	return result;
}

static int hp_lps0_enter(struct hp_lps0_sequence *sequence)
{
	static const unsigned int entries[] = { 3, 7, 5 };
	static const unsigned int unwind[] = {
		(1U << 9) | (1U << 4), 1U << 8, 1U << 6
	};
	unsigned int i;
	int ret;

	/* Never start a new cycle over an unacknowledged exit. */
	ret = hp_lps0_restore(sequence);
	if (ret)
		return ret;
	for (i = 0; i < sizeof(entries) / sizeof(entries[0]); ++i) {
		/* Failed AML evaluations can already have changed the EC. */
		sequence->pending |= unwind[i];
		ret = sequence->notify(sequence->context, entries[i]);
		if (ret) {
			hp_lps0_restore(sequence);
			return ret;
		}
	}
	return 0;
}

#endif
