build_lib_example(
  NAME qsaqmaodv
  SOURCE_FILES qsaqmaodv.cc
  LIBRARIES_TO_LINK
    ${libwifi}
    ${libinternet}
    ${libqsaqmaodv}
    ${libinternet-apps}
)
