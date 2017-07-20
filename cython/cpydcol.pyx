import numpy as np
cimport numpy as np
cimport cython

@cython.boundscheck(False)
@cython.wraparound(False)
cdef np.ndarray[np.float32_t,ndim = 1] dcol_matrix_order(np.ndarray[np.float32_t,ndim=2] array,np.ndarray[np.float32_t,ndim=1] row,int ncol):
    cdef np.ndarray[np.float32_t,ndim=2] sorted_mat = array[:,np.argsort(row)]
    cdef np.ndarray[np.float32_t,ndim=2] d = np.abs(sorted_mat[:,1:] - sorted_mat[:,0:(ncol-1)])
    cdef np.ndarray[np.float32_t,ndim=1] dd = np.sum(d,axis=1)/(ncol - 1)
    return dd

@cython.boundscheck(False)
@cython.wraparound(False)
cdef np.ndarray[np.float32_t,ndim = 2] _dcol_matrix(int nrow,int ncol,np.ndarray[np.float32_t,ndim=2] array):
    cdef np.ndarray[np.float32_t, ndim=2] dcolmat = np.zeros((nrow,nrow),dtype=np.float32)

    for i in xrange(nrow):
      dcolmat[i,:] = dcol_matrix_order(array,array[i,:],ncol)

    return dcolmat


def dcol(array):
  nrow = array.shape[0]
  ncol = array.shape[1]
  return _dcol_matrix(nrow,ncol,array)
