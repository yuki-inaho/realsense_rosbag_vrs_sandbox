// pyvrs_writer/src/bindings.cpp
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "vrs_writer.h"

namespace py = pybind11;

PYBIND11_MODULE(_pyvrs_writer, m) {
  m.doc() = "Python bindings for VRS file writer";

  py::class_<pyvrs_writer::VRSWriter>(m, "VRSWriter")
    .def(py::init<const std::string&>(),
         py::arg("filepath"),
         "Create a new VRS file")

    .def("add_stream",
         &pyvrs_writer::VRSWriter::addStream,
         py::arg("stream_id"),
         py::arg("stream_name"),
         "Add a new stream to the VRS file")

    .def("write_configuration",
         &pyvrs_writer::VRSWriter::writeConfiguration,
         py::arg("stream_id"),
         py::arg("json_config"),
         "Write a configuration record")

    .def("write_data",
         &pyvrs_writer::VRSWriter::writeData,
         py::arg("stream_id"),
         py::arg("timestamp"),
         py::arg("data"),
         "Write a data record")

    .def("close",
         &pyvrs_writer::VRSWriter::close,
         "Close the VRS file")

    .def("is_open",
         &pyvrs_writer::VRSWriter::isOpen,
         "Check if the file is open")

    .def("__enter__",
         [](pyvrs_writer::VRSWriter& self) -> pyvrs_writer::VRSWriter& {
           return self;
         })

    .def("__exit__",
         [](pyvrs_writer::VRSWriter& self, py::object, py::object, py::object) {
           self.close();
         });
}
