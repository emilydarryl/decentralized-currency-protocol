# Copyright (c) 2025-present The Bitcoin Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.

include_guard(GLOBAL)
include(GNUInstallDirs)

function(install_binary_component component)
  cmake_parse_arguments(PARSE_ARGV 1
    IC                          # prefix
    "HAS_MANPAGE;INTERNAL"      # options
    "MANPAGE"                   # one_value_keywords
    ""                          # multi_value_keywords
  )
  set(target_name ${component})
  if(IC_MANPAGE AND NOT IC_HAS_MANPAGE)
    message(FATAL_ERROR "MANPAGE requires HAS_MANPAGE for target ${target_name}")
  endif()
  if(IC_INTERNAL)
    set(runtime_dest ${CMAKE_INSTALL_LIBEXECDIR})
  else()
    set(runtime_dest ${CMAKE_INSTALL_BINDIR})
  endif()
  install(TARGETS ${target_name}
    RUNTIME DESTINATION ${runtime_dest}
    COMPONENT ${component}
  )
  if(INSTALL_MAN AND IC_HAS_MANPAGE)
    if(IC_MANPAGE)
      set(manpage_name ${IC_MANPAGE})
    else()
      set(manpage_name ${target_name})
    endif()
    set(manpage_path "${PROJECT_SOURCE_DIR}/doc/man/${manpage_name}.1")
    if(NOT EXISTS "${manpage_path}")
      message(FATAL_ERROR "Missing manual page for ${target_name}: ${manpage_path}")
    endif()
    install(FILES "${manpage_path}"
      DESTINATION ${CMAKE_INSTALL_MANDIR}/man1
      COMPONENT ${component}
    )
  endif()
endfunction()
