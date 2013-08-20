#include <Python.h>

static PyMethodDef PodMethods[] = {
    {NULL, NULL, 0, NULL}        /* Sentinel */
};

PyMODINIT_FUNC initopuspb(void)
{
    PyObject *m;

    m = Py_InitModule("opuspb", PodMethods);
    if (m == NULL)
        return;
}
