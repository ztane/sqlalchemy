/*
loader.c
Copyright (C) 2014 the SQLAlchemy authors and contributors <see AUTHORS file>

This module is part of SQLAlchemy and is released under
the MIT License: http://www.opensource.org/licenses/mit-license.php
*/

#include <Python.h>
#include <stdio.h>

#define MODULE_NAME "cloader"
#define MODULE_DOC "Module containing C versions of ORM loading."


static PyObject * populate_full(PyObject *self, PyObject *args) {

	PyObject *context;
	PyObject *load_path;
	PyObject *row;
	PyObject *state;
	PyObject *dict_;
	PyObject *isnew;
	PyObject *loaded_instance;
	PyObject *populate_existing;
	PyObject *populators;

	int isnew_bool;
	PyObject *runid;
	PyObject *propagate_options;
	int propagate_options_bool;
	PyObject *load_options;
	int load_options_bool;

	PyObject *populator_collection;

	PyObject *seq;
	PyObject *seq_item;
	PyObject *key;
	PyObject *getter;
	int len;
	int i;

	PyObject *arglist;
	PyObject *retvalue;

	if (!PyArg_UnpackTuple(args, "populate_full", 9, 9,
			&context, &load_path, &row,
			&state, &dict_, &isnew,
			&loaded_instance, &populate_existing,
			&populators
		)) {
		return NULL;
	}


	isnew_bool = PyObject_IsTrue(isnew);
	if (isnew_bool == -1) {
		return NULL;
	}
	/* if isnew:
        	# first time we are seeing a row with this identity.
     */

	else if (isnew_bool == 1) {

        /* state.runid = context.runid */

		runid = PyObject_GetAttrString(context, "runid");
		if (runid == NULL)
			return NULL;

		if (PyObject_SetAttrString(state, "runid", runid) == -1) {
			Py_DECREF(runid);
			return NULL;
		}

        /* if context.propagate_options:
            state.load_options = context.propagate_options */

		propagate_options = PyObject_GetAttrString(context, "propagate_options");
		if (propagate_options == NULL)
			return NULL;
		propagate_options_bool = PyObject_IsTrue(propagate_options);
		if (propagate_options_bool == -1)
			return NULL;
		else if (propagate_options_bool == 1) {
			if (PyObject_SetAttrString(state, "load_options", propagate_options) == -1)	{
				Py_DECREF(propagate_options);
				return NULL;
			}
		}
		else {
			Py_DECREF(propagate_options);
		}

        /* if state.load_options:
            state.load_path = load_path */

		load_options = PyObject_GetAttrString(state, "load_options");
		if (load_options == NULL)
			return NULL;
		load_options_bool = PyObject_IsTrue(load_options);
		if (load_options_bool == -1)
			return NULL;
		else if (load_options_bool == 1) {
			if (PyObject_SetAttrString(state, "load_path", load_path) == -1)	{
				Py_DECREF(load_options);
				return NULL;
			}
		}
		Py_DECREF(load_options);

        /*for key, getter in populators["quick"]: */
		populator_collection = PyDict_GetItemString(populators, "quick");
		if (populator_collection == NULL)
			return NULL;
		seq = PySequence_Fast(populator_collection, "expected a sequence");
		if (seq == NULL)
			return NULL;


    	len = PySequence_Fast_GET_SIZE(seq);
    	for (i = 0; i < len; i++) {
    		seq_item = PySequence_Fast_GET_ITEM(seq, i);
    		key = PyTuple_GET_ITEM(seq_item, 0);
    		getter = PyTuple_GET_ITEM(seq_item, 1);

    		if (key == NULL || getter == NULL) {
    			Py_DECREF(seq);
    			return NULL;
    		}

    		arglist = Py_BuildValue("(O)", row);
    		if (arglist == NULL) {
    			Py_DECREF(seq);
    			return NULL;
    		}
			retvalue = PyObject_CallObject(getter, arglist);
			Py_DECREF(arglist);
			if (retvalue == NULL) {
		    	Py_DECREF(seq);
				return NULL;
			}

			/* dict_[key] = getter(row) */
			PyDict_SetItem(dict_, key, retvalue);
    	}
    	Py_DECREF(seq);

        /* if populate_existing: */
            /* for key, set_callable in populators["expire"]:
                dict_.pop(key, None) */
                /* if set_callable:
                    state.callables[key] = state */
        /* else: */
            /* for key, set_callable in populators["expire"]: */
                /* if set_callable:
                    state.callables[key] = state */
        /* for key, populator in populators["new"]:
            populator(state, dict_, row) */
        /* for key, populator in populators["delayed"]:
            populator(state, dict_, row) */


	}
	else {


	}

	Py_RETURN_NONE;
}

/*
def _populate_full(
        context, load_path, row, state, dict_, isnew,
        loaded_instance, populate_existing, populators):
    if isnew:
        # first time we are seeing a row with this identity.
        state.runid = context.runid
        if context.propagate_options:
            state.load_options = context.propagate_options
        if state.load_options:
            state.load_path = load_path

        for key, getter in populators["quick"]:
            dict_[key] = getter(row)
        if populate_existing:
            for key, set_callable in populators["expire"]:
                dict_.pop(key, None)
                if set_callable:
                    state.callables[key] = state
        else:
            for key, set_callable in populators["expire"]:
                if set_callable:
                    state.callables[key] = state
        for key, populator in populators["new"]:
            populator(state, dict_, row)
        for key, populator in populators["delayed"]:
            populator(state, dict_, row)

    else:
        # have already seen rows with this identity.
        for key, populator in populators["existing"]:
            populator(state, dict_, row)
*/

static PyMethodDef module_methods[] = {
    {"_populate_full", populate_full, METH_VARARGS,
	 "Run ORM population for a new row."},
    {NULL, NULL, 0, NULL}        /* Sentinel */
};

#ifndef PyMODINIT_FUNC  /* declarations for DLL import/export */
#define PyMODINIT_FUNC void
#endif

#if PY_MAJOR_VERSION >= 3

static struct PyModuleDef module_def = {
    PyModuleDef_HEAD_INIT,
    MODULE_NAME,
    MODULE_DOC,
    -1,
    module_methods
 };
#endif


#if PY_MAJOR_VERSION >= 3
PyMODINIT_FUNC
PyInit_cloader(void)
#else
PyMODINIT_FUNC
initcloader(void)
#endif
{
    PyObject *m;

#if PY_MAJOR_VERSION >= 3
    m = PyModule_Create(&module_def);
#else
    m = Py_InitModule3(MODULE_NAME, module_methods, MODULE_DOC);
#endif

#if PY_MAJOR_VERSION >= 3
    if (m == NULL)
        return NULL;
    return m;
#else
    if (m == NULL)
    	return;
#endif
}

