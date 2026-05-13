package main

func completionExtract(v any) []string {
	var out []string
	seen := map[string]bool{}
	var walk func(any, string)
	walk = func(x any, key string) {
		switch t := x.(type) {
		case string:
			if completionIsKey(key) && t != "" && !seen[t] {
				seen[t] = true
				out = append(out, t)
			}
		case []any:
			for _, item := range t {
				walk(item, key)
			}
		case map[string]any:
			if textEdit, ok := t["textEdit"]; ok {
				walk(textEdit, "textEdit")
			}
			for _, k := range []string{"newText", "insertText", "generated_text", "generatedText", "completion", "text", "label"} {
				if val, ok := t[k]; ok {
					walk(val, k)
				}
			}
			for k, val := range t {
				if k != "documentation" && k != "detail" {
					walk(val, k)
				}
			}
		}
	}
	walk(v, "")
	return out
}

func completionIsKey(k string) bool {
	switch k {
	case "newText", "insertText", "generated_text", "generatedText", "completion", "text", "label", "textEdit":
		return true
	default:
		return false
	}
}
