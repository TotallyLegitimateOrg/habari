package main

/*
#include <stdlib.h>
*/
import "C"

import (
	"encoding/json"
	"unsafe"

	habari "github.com/TotallyLegitimateOrg/habari"
)

//export HabariParseJSON
func HabariParseJSON(filename *C.char) *C.char {
	if filename == nil {
		return C.CString("{}")
	}

	metadata := habari.Parse(C.GoString(filename))
	data, err := json.Marshal(metadata)
	if err != nil {
		return C.CString("{}")
	}

	return C.CString(string(data))
}

//export HabariFree
func HabariFree(ptr *C.char) {
	if ptr != nil {
		C.free(unsafe.Pointer(ptr))
	}
}

func main() {}
