/*
 * Copyright (c) 2026 Nordic Semiconductor ASA
 *
 * SPDX-License-Identifier: Apache-2.0
 *
 * Shared application built for every core (cpuapp, cpurad, cpuppr, cpuflpr).
 * Each core simply emits log messages periodically. With STM multi-domain
 * logging the messages from all cores are multiplexed in hardware, drained by
 * the application core (the ETR proxy) and sent out over a single UART.
 *
 * The originating core is identified on the host by the STM decoder prefix
 * (app / rad / ppr / flpr), so the log strings themselves stay generic.
 */

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

LOG_MODULE_REGISTER(h20_log, LOG_LEVEL_DBG);

int main(void)
{
	unsigned int cnt = 0U;

	LOG_INF("Core online, starting heartbeat");

	while (1) {
		LOG_INF("heartbeat %u", cnt);
		LOG_DBG("debug detail for iteration %u", cnt);

		if ((cnt % 10U) == 0U) {
			LOG_WRN("milestone reached at %u", cnt);
		}

		cnt++;
		k_sleep(K_MSEC(1000));
	}

	return 0;
}
