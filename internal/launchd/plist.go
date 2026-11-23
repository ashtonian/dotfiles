// Package launchd reads LaunchAgent property lists and registers them with
// the user's launchd GUI domain through launchctl.
package launchd

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/xml"
	"errors"
	"fmt"
	"io"
	"strings"
)

// Job is what dotfiles needs from a LaunchAgent's property list.
type Job struct {
	Label             string
	StandardOutPath   string
	StandardErrorPath string
	// KeepAlive is set when launchd keeps the job running (KeepAlive is true
	// or a dictionary of conditions): a service, which a reload restarts,
	// rather than a job that runs on a schedule and exits.
	KeepAlive bool
}

// Read parses an XML property list with a dictionary at its root.
func Read(data []byte) (Job, error) {
	var job Job
	dec := xml.NewDecoder(bytes.NewReader(data))
	if err := expectStart(dec, "plist"); err != nil {
		return job, err
	}
	if err := expectStart(dec, "dict"); err != nil {
		return job, err
	}
	strs := map[string]*string{"Label": &job.Label, "StandardOutPath": &job.StandardOutPath, "StandardErrorPath": &job.StandardErrorPath}
	for {
		tok, err := nextElement(dec)
		if err != nil {
			return job, err
		}
		if end, ok := tok.(xml.EndElement); ok && end.Name.Local == "dict" {
			return job, nil
		}
		start, ok := tok.(xml.StartElement)
		if !ok || start.Name.Local != "key" {
			return job, fmt.Errorf("property list: want <key> in the root dictionary, got %v", tok)
		}
		var key string
		if err := dec.DecodeElement(&key, &start); err != nil {
			return job, fmt.Errorf("property list: %w", err)
		}
		tok, err = nextElement(dec)
		if err != nil {
			return job, err
		}
		value, ok := tok.(xml.StartElement)
		if !ok {
			return job, fmt.Errorf("property list: key %q has no value", key)
		}
		if dst, ok := strs[key]; ok {
			if value.Name.Local != "string" {
				return job, fmt.Errorf("property list: %s is <%s>, want <string>", key, value.Name.Local)
			}
			if err := dec.DecodeElement(dst, &value); err != nil {
				return job, fmt.Errorf("property list: %s: %w", key, err)
			}
			continue
		}
		if key == "KeepAlive" {
			job.KeepAlive = value.Name.Local == "true" || value.Name.Local == "dict"
		}
		if err := dec.Skip(); err != nil {
			return job, fmt.Errorf("property list: %s: %w", key, err)
		}
	}
}

// nextElement returns the next start or end element, skipping whitespace,
// comments, the XML declaration and the DOCTYPE.
func nextElement(dec *xml.Decoder) (xml.Token, error) {
	for {
		tok, err := dec.Token()
		if errors.Is(err, io.EOF) {
			return nil, errors.New("property list: ends inside the root dictionary")
		}
		if err != nil {
			return nil, fmt.Errorf("property list: %w", err)
		}
		switch t := tok.(type) {
		case xml.StartElement, xml.EndElement:
			return t, nil
		case xml.CharData:
			if text := strings.TrimSpace(string(t)); text != "" {
				return nil, fmt.Errorf("property list: unexpected text %q", text)
			}
		}
	}
}

func expectStart(dec *xml.Decoder, name string) error {
	tok, err := nextElement(dec)
	if err != nil {
		return err
	}
	if start, ok := tok.(xml.StartElement); !ok || start.Name.Local != name {
		return fmt.Errorf("property list: want <%s>, got %v", name, tok)
	}
	return nil
}

// containers are the property list elements that hold other elements.
var containers = map[string]bool{"plist": true, "dict": true, "array": true}

// Definition fingerprints what launchd reads from a property list: its
// elements, attributes and values, without comments, the XML declaration, the
// DOCTYPE, or the whitespace that only lays elements out. Two plists with one
// definition run the same job, so a change to a template's comments needs no
// reload.
func Definition(data []byte) (string, error) {
	dec := xml.NewDecoder(bytes.NewReader(data))
	sum := sha256.New()
	var open []string
	for {
		tok, err := dec.Token()
		if errors.Is(err, io.EOF) {
			if len(open) > 0 {
				return "", errors.New("property list: ends inside <" + open[len(open)-1] + ">")
			}
			return hex.EncodeToString(sum.Sum(nil)), nil
		}
		if err != nil {
			return "", fmt.Errorf("property list: %w", err)
		}
		switch t := tok.(type) {
		case xml.StartElement:
			open = append(open, t.Name.Local)
			fmt.Fprintf(sum, "<%s", t.Name.Local)
			for _, a := range t.Attr {
				fmt.Fprintf(sum, " %s=%q", a.Name.Local, a.Value)
			}
			sum.Write([]byte{'>'})
		case xml.EndElement:
			open = open[:len(open)-1]
			fmt.Fprintf(sum, "</%s>", t.Name.Local)
		case xml.CharData:
			// Text between a container's elements lays them out; inside any
			// other element (key, string, integer, real, date, data) it is a value.
			if len(open) > 0 && !containers[open[len(open)-1]] {
				fmt.Fprintf(sum, "%q", string(t))
			}
		}
	}
}
