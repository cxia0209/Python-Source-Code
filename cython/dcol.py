import numpy as np

def dcol_matrix_order(row,array,nrow,ncol):
    index_sort = np.argsort(row)
    if(np.isnan(nrow) or nrow == 1):
        sorted_array = array[index_sort]
        d = sorted_array[1:] - sorted_array[0:len(sorted_array)-1]
        dd = np.sum(np.abs(d))/(ncol-1)
    else:
        sorted_mat = array[:,index_sort]
        d = sorted_mat[:,1:] - sorted_mat[:,0:(ncol-1)]
        dd = np.apply_along_axis(np.sum,1,abs(d))/(ncol - 1)
    return dd

def dcol_matrix(array):
    nrow = array.shape[0]
    ncol = array.shape[1]
    rdmat = np.zeros((nrow,nrow))
    dcolmat = np.apply_along_axis(dcol_matrix_order,1,array,array,nrow,ncol)
    return dcolmat
