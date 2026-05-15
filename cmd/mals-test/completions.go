package main

var completionTextFields = []string{
	"newText",
	"insertText",
	"generated_text",
	"generatedText",
	"completion",
	"text",
	"label",
}

var completionTextFieldSet = func() map[string]bool {
	fields := map[string]bool{}
	for _, field := range completionTextFields {
		fields[field] = true
	}
	return fields
}()

func completionExtract(v any) []string {
	var completions []string
	seen := map[string]bool{}
	var walk func(any, string)
	walk = func(value any, fieldName string) {
		switch t := value.(type) {
		case string:
			if completionIsTextField(fieldName) && t != "" && !seen[t] {
				seen[t] = true
				completions = append(completions, t)
			}
		case []any:
			for _, item := range t {
				walk(item, fieldName)
			}
		case map[string]any:
			if textEdit, ok := t["textEdit"]; ok {
				walk(textEdit, "")
			}
			for _, field := range completionTextFields {
				if val, ok := t[field]; ok {
					walk(val, field)
				}
			}
			for field, val := range t {
				if field != "documentation" && field != "detail" {
					walk(val, field)
				}
			}
		}
	}
	walk(v, "")
	return completions
}

func completionIsTextField(fieldName string) bool {
	return completionTextFieldSet[fieldName]
}
