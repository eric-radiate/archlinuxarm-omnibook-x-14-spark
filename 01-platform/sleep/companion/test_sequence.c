/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "lps0_sequence.h"

struct mock {
	unsigned int calls[64];
	unsigned int count;
	unsigned int fail;
};

static int notify(void *context, unsigned int function)
{
	struct mock *mock = context;
	assert(mock->count < 64);
	mock->calls[mock->count++] = function;
	return mock->fail & (1U << function) ? -5 : 0;
}

int main(void)
{
	struct mock mock = {0};
	struct hp_lps0_sequence sequence = { .context = &mock, .notify = notify };
	const unsigned int expected[] = {3, 7, 5, 6, 9, 8, 4};
	unsigned int function, i;

	assert(hp_lps0_enter(&sequence) == 0);
	assert(hp_lps0_restore(&sequence) == 0);
	assert(sequence.pending == 0);
	assert(mock.count == 7 && !memcmp(mock.calls, expected, sizeof(expected)));
	/* A second completion must not issue duplicate exits. */
	assert(hp_lps0_restore(&sequence) == 0 && mock.count == 7);
	/* Every partial-entry failure must restore exactly the attempted state. */
	for (i = 0; i < 3; ++i) {
		memset(&mock, 0, sizeof(mock));
		mock.fail = 1U << expected[i];
		assert(hp_lps0_enter(&sequence) == -5);
		assert(sequence.pending == 0);
		for (function = 0; function <= i; ++function)
			assert(mock.calls[function] == expected[function]);
		for (function = i + 1; function < mock.count; ++function)
			assert(mock.calls[function] != 3 && mock.calls[function] != 7 &&
			       mock.calls[function] != 5);
	}
	/* Each failed exit remains pending; another entry must be refused. */
	for (i = 3; i < 7; ++i) {
		memset(&mock, 0, sizeof(mock));
		assert(hp_lps0_enter(&sequence) == 0);
		mock.fail = 1U << expected[i];
		assert(hp_lps0_restore(&sequence) == -5);
		assert(sequence.pending == mock.fail);
		mock.count = 0;
		assert(hp_lps0_enter(&sequence) == -5);
		assert(mock.count == 1 && mock.calls[0] == expected[i]);
		mock.fail = 0;
		assert(hp_lps0_restore(&sequence) == 0);
		assert(sequence.pending == 0);
	}
	/* Failed entry plus failed unwind keeps the exit for complete/retry. */
	memset(&mock, 0, sizeof(mock));
	mock.fail = (1U << 7) | (1U << 8);
	assert(hp_lps0_enter(&sequence) == -5);
	assert(sequence.pending == (1U << 8));
	mock.fail = 0;
	assert(hp_lps0_restore(&sequence) == 0 && sequence.pending == 0);
	/* Repeated complete cycles remain balanced. */
	for (i = 0; i < 100; ++i) {
		memset(&mock, 0, sizeof(mock));
		assert(hp_lps0_enter(&sequence) == 0);
		assert(hp_lps0_restore(&sequence) == 0);
		assert(mock.count == 7 && !memcmp(mock.calls, expected, sizeof(expected)));
	}
	puts("LPS0 order, entry failures, exit retries and 100 repeated cycles passed");
	return 0;
}
