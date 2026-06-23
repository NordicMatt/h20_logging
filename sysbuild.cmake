#
# Copyright (c) 2026 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: Apache-2.0
#

include_guard(GLOBAL)

# Build the same application for the Radio, PPR and FLPR cores in addition to
# the default (application core) image. All four images share this source
# directory; per-core configuration is selected automatically from the matching
# boards/<board_target>.conf and boards/<board_target>.overlay files.

if(SB_CONFIG_APP_CPURAD_RUN)
  ExternalZephyrProject_Add(
    APPLICATION h20_logging_${SB_CONFIG_NETCORE_REMOTE_BOARD_TARGET_CPUCLUSTER}
    SOURCE_DIR ${APP_DIR}
    BOARD ${SB_CONFIG_BOARD}/${SB_CONFIG_SOC}/${SB_CONFIG_NETCORE_REMOTE_BOARD_TARGET_CPUCLUSTER}
    BOARD_REVISION ${BOARD_REVISION}
  )
endif()

if(SB_CONFIG_APP_CPUPPR_RUN)
  ExternalZephyrProject_Add(
    APPLICATION h20_logging_${SB_CONFIG_PPRCORE_REMOTE_BOARD_TARGET_CPUCLUSTER}
    SOURCE_DIR ${APP_DIR}
    BOARD ${SB_CONFIG_BOARD}/${SB_CONFIG_SOC}/${SB_CONFIG_PPRCORE_REMOTE_BOARD_TARGET_CPUCLUSTER}
    BOARD_REVISION ${BOARD_REVISION}
  )
endif()

if(SB_CONFIG_APP_CPUFLPR_RUN)
  ExternalZephyrProject_Add(
    APPLICATION h20_logging_${SB_CONFIG_FLPRCORE_REMOTE_BOARD_TARGET_CPUCLUSTER}
    SOURCE_DIR ${APP_DIR}
    BOARD ${SB_CONFIG_BOARD}/${SB_CONFIG_SOC}/${SB_CONFIG_FLPRCORE_REMOTE_BOARD_TARGET_CPUCLUSTER}
    BOARD_REVISION ${BOARD_REVISION}
  )
endif()
