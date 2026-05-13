package main

import (
	"regexp"
	"strings"
)

var identifierRE = regexp.MustCompile(`[A-Za-z_][A-Za-z0-9_]*`)

var keywordSet = map[string]bool{
	"abstract": true, "as": true, "assert": true, "async": true, "await": true,
	"bool": true, "boolean": true, "break": true, "case": true, "catch": true,
	"char": true, "class": true, "const": true, "continue": true, "def": true,
	"default": true, "defer": true, "do": true, "double": true, "else": true,
	"enum": true, "extends": true, "false": true, "final": true, "finally": true,
	"float": true, "fn": true, "for": true, "func": true, "go": true, "if": true,
	"implements": true, "import": true, "in": true, "int": true, "interface": true,
	"let": true, "long": true, "namespace": true, "new": true, "nil": true,
	"none": true, "null": true, "package": true, "private": true, "protected": true,
	"public": true, "return": true, "static": true, "struct": true, "switch": true,
	"this": true, "throw": true, "throws": true, "true": true, "try": true,
	"type": true, "using": true, "var": true, "void": true, "while": true,
}

func scoreCompletion(pred, ref string) metrics {
	pred = strings.TrimSpace(pred)
	ref = strings.TrimSpace(ref)
	predIDs := identifiers(pred)
	refIDs := identifiers(ref)
	return metrics{
		ExactMatch:           boolFloat(pred == ref),
		EditSimilarity:       editSimilarity(pred, ref),
		IdentifierExactMatch: boolFloat(equalStrings(predIDs, refIDs)),
		IdentifierF1:         identifierF1(predIDs, refIDs),
	}
}

func identifiers(text string) []string {
	raw := identifierRE.FindAllString(text, -1)
	out := make([]string, 0, len(raw))
	for _, item := range raw {
		if !keywordSet[strings.ToLower(item)] {
			out = append(out, item)
		}
	}
	return out
}

func editSimilarity(a, b string) float64 {
	ar := []rune(a)
	br := []rune(b)
	maxLen := max(len(br), len(ar))
	if maxLen == 0 {
		return 1
	}
	dist := levenshtein(ar, br)
	return 1 - float64(dist)/float64(maxLen)
}

func levenshtein(a, b []rune) int {
	if len(a) == 0 {
		return len(b)
	}
	if len(b) == 0 {
		return len(a)
	}
	prev := make([]int, len(b)+1)
	curr := make([]int, len(b)+1)
	for j := range prev {
		prev[j] = j
	}
	for i := 1; i <= len(a); i++ {
		curr[0] = i
		for j := 1; j <= len(b); j++ {
			cost := 0
			if a[i-1] != b[j-1] {
				cost = 1
			}
			curr[j] = minInt(curr[j-1]+1, prev[j]+1, prev[j-1]+cost)
		}
		prev, curr = curr, prev
	}
	return prev[len(b)]
}

func identifierF1(pred, ref []string) float64 {
	if len(pred) == 0 && len(ref) == 0 {
		return 1
	}
	if len(pred) == 0 || len(ref) == 0 {
		return 0
	}
	refCounts := map[string]int{}
	for _, item := range ref {
		refCounts[item]++
	}
	overlap := 0
	for _, item := range pred {
		if refCounts[item] > 0 {
			overlap++
			refCounts[item]--
		}
	}
	if overlap == 0 {
		return 0
	}
	precision := float64(overlap) / float64(len(pred))
	recall := float64(overlap) / float64(len(ref))
	return 2 * precision * recall / (precision + recall)
}

func boolFloat(v bool) float64 {
	if v {
		return 1
	}
	return 0
}

func equalStrings(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}

func minInt(values ...int) int {
	best := values[0]
	for _, value := range values[1:] {
		if value < best {
			best = value
		}
	}
	return best
}
