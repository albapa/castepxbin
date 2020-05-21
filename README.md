castepxbin
==========================

A collection of readers for CASTEP binary output from CASTEP.
At the moment, there is only the reader for `pdos_dos` file available.
This file contains the weights of the eigenvalues on  each projected orbitals,
which can be used to constructed projected density of states.

The hope of this this repository is to provide, possibly, a collection of readers
for the binary outputs. The code for `pdos_bin` can be used as a example, and 
it should be straight forward to implement readers for other files such as 
`ome_bin`, `dome_bin` etc.

DISCLAIMER: The structure of the binary `pdos_bin` file is inferred from the code snippet 
in the documentation of the open source [OptaDos](https://github.com/optados-developers/optados) packages.