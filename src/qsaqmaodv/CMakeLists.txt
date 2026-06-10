build_lib(
  LIBNAME qsaqmaodv
  SOURCE_FILES
    model/qsaqmaodv-rtable.cc
    model/qsaqmaodv-rqueue.cc
    model/qsaqmaodv-packet.cc
    model/qsaqmaodv-qtable.cc
    model/qsaqmaodv-id-cache.cc
    model/qsaqmaodv-dpd.cc
    model/qsaqmaodv-neighbor.cc
    model/qsaqmaodv-routing-protocol.cc
    helper/qsaqmaodv-helper.cc
  HEADER_FILES
    model/qsaqmaodv-rtable.h
    model/qsaqmaodv-rqueue.h
    model/qsaqmaodv-packet.h
    model/qsaqmaodv-qtable.h
    model/qsaqmaodv-id-cache.h
    model/qsaqmaodv-dpd.h
    model/qsaqmaodv-neighbor.h
    model/qsaqmaodv-routing-protocol.h
    helper/qsaqmaodv-helper.h
  LIBRARIES_TO_LINK ${libinternet}
                  ${libwifi}
)
