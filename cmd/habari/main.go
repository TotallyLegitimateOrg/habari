package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"reflect"
	"strings"

	"github.com/TotallyLegitimateOrg/habari"
)

func main() {
	jsonOutput := flag.Bool("json", false, "Output as JSON")
	flag.Usage = func() {
		fmt.Fprintf(os.Stderr, "Usage: habari [--json] <filename>\n\n")
	}
	flag.Parse()

	args := flag.Args()
	if len(args) != 1 {
		flag.Usage()
		os.Exit(1)
	}

	m := habari.Parse(args[0])

	if *jsonOutput {
		enc := json.NewEncoder(os.Stdout)
		enc.SetIndent("", "  ")
		enc.SetEscapeHTML(false)
		if err := enc.Encode(m); err != nil {
			fmt.Fprintf(os.Stderr, "Error encoding JSON: %v\n", err)
			os.Exit(1)
		}
	} else {
		printMetadata(m)
	}
}

func printMetadata(m *habari.Metadata) {
	v := reflect.ValueOf(*m)
	t := v.Type()

	type pair struct {
		label string
		value string
	}

	var pairs []pair
	maxLen := 0

	for i := 0; i < t.NumField(); i++ {
		field := t.Field(i)
		val := v.Field(i)

		var str string
		switch val.Kind() {
		case reflect.String:
			str = val.String()
		case reflect.Slice:
			parts := make([]string, val.Len())
			for j := 0; j < val.Len(); j++ {
				parts[j] = val.Index(j).String()
			}
			str = strings.Join(parts, ", ")
		}

		if str == "" {
			continue
		}

		label := field.Name
		pairs = append(pairs, pair{label, str})
		if len(label) > maxLen {
			maxLen = len(label)
		}
	}

	for _, p := range pairs {
		fmt.Printf("  %-*s  %s\n", maxLen+1, p.label+":", p.value)
	}
}
