package launchd

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestReadTakesTheRootDictionarysJobKeys(t *testing.T) {
	plist := `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<!-- A comment, as the templates have. -->
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.example.job</string>
    <key>ProgramArguments</key>
    <array><string>/bin/echo</string><string>hi</string></array>
    <key>EnvironmentVariables</key>
    <dict><key>StandardOutPath</key><string>/nested/is/not/the/job's</string></dict>
    <key>KeepAlive</key>
    <dict><key>PathState</key><dict><key>/tmp/x</key><true/></dict></dict>
    <key>StandardOutPath</key>
    <string>/Users/me/Library/Logs/job/out.log</string>
</dict>
</plist>
`
	got, err := Read([]byte(plist))
	require.NoError(t, err)
	assert.Equal(t, Job{Label: "com.example.job", StandardOutPath: "/Users/me/Library/Logs/job/out.log", KeepAlive: true}, got)
}

func TestReadKeepAlive(t *testing.T) {
	for value, want := range map[string]bool{"<true/>": true, "<false/>": false, "<dict/>": true, "": false} {
		t.Run(value, func(t *testing.T) {
			keep := ""
			if value != "" {
				keep = "<key>KeepAlive</key>" + value
			}
			got, err := Read([]byte("<plist><dict><key>Label</key><string>x</string>" + keep + "</dict></plist>"))
			require.NoError(t, err)
			assert.Equal(t, want, got.KeepAlive)
		})
	}
}

func TestReadRejectsWhatIsNotAPropertyList(t *testing.T) {
	for name, data := range map[string]string{
		"not xml":           "Label = x",
		"no dict":           "<plist><array/></plist>",
		"key without value": "<plist><dict><key>Label</key></dict></plist>",
		"truncated":         "<plist><dict><key>Label</key><string>x</string>",
		"a label not text":  "<plist><dict><key>Label</key><integer>1</integer></dict></plist>",
	} {
		t.Run(name, func(t *testing.T) {
			_, err := Read([]byte(data))
			assert.Error(t, err)
		})
	}
}

func TestDefinitionIgnoresCommentsAndLayout(t *testing.T) {
	base := "<plist version=\"1.0\"><dict><key>Label</key><string>com.example.job</string><key>RunAtLoad</key><true/>" +
		"<key>Nice</key><integer>10</integer><key>Args</key><array><string>a</string></array></dict></plist>"
	same := `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<!-- installed by something else -->
<plist version="1.0">
<dict>
    <!-- Unique identifier for this job -->
    <key>Label</key>
    <string>com.example.job</string>
    <key>RunAtLoad</key>
    <true/>
    <key>Nice</key>
    <integer>10</integer>
    <key>Args</key>
    <array>
        <string>a</string>
    </array>
</dict>
</plist>
`
	want, err := Definition([]byte(base))
	require.NoError(t, err)
	got, err := Definition([]byte(same))
	require.NoError(t, err)
	assert.Equal(t, want, got)

	for name, other := range map[string]string{
		"a value":         strings.Replace(base, "com.example.job", "com.example.other", 1),
		"a value's space": strings.Replace(base, "<string>com.example.job</string>", "<string>com.example.job </string>", 1),
		"a boolean":       strings.Replace(base, "<true/>", "<false/>", 1),
		"a number":        strings.Replace(base, "<integer>10</integer>", "<integer>20</integer>", 1),
		"a key":           strings.Replace(base, "<key>Nice</key>", "<key>LowPriorityIO</key>", 1),
		"an attribute":    strings.Replace(base, `version="1.0"`, `version="2.0"`, 1),
	} {
		t.Run(name, func(t *testing.T) {
			got, err := Definition([]byte(other))
			require.NoError(t, err)
			assert.NotEqual(t, want, got)
		})
	}
	_, err = Definition([]byte("<plist><dict>"))
	assert.Error(t, err)
}

// fakeLaunchctl writes a launchctl stand-in that records its arguments and
// keeps loaded labels as files in a directory; a label whose file says
// "running" prints as running. A bootstrap fails while the countdown in the
// failures file is above zero.
type fakeLaunchctl struct {
	path, audit, loaded, failures string
}

func newFakeLaunchctl(t *testing.T) *fakeLaunchctl {
	t.Helper()
	dir := t.TempDir()
	f := &fakeLaunchctl{path: filepath.Join(dir, "launchctl"), audit: filepath.Join(dir, "audit"),
		loaded: filepath.Join(dir, "loaded"), failures: filepath.Join(dir, "failures")}
	require.NoError(t, os.Mkdir(f.loaded, 0o700))
	script := fmt.Sprintf(`#!/bin/sh
printf '%%s\n' "$*" >> %[1]q
case $1 in
print)
	job=%[2]q/"${2##*/}"
	[ -f "$job" ] || { echo "Could not find service" >&2; exit 113; }
	state="not running"; [ "$(cat "$job")" = running ] && state=running
	printf 'gui/501/%%s = {\n\tactive count = 0\n\tstate = %%s\n\tendpoints = {\n\t\tstate = active\n\t}\n}\n' "${2##*/}" "$state" ;;
bootout) [ -f %[2]q/"${2##*/}" ] || { echo "Boot-out failed: 3: No such process" >&2; exit 3; }; rm %[2]q/"${2##*/}" ;;
bootstrap)
	n=$(cat %[3]q 2>/dev/null || echo 0)
	if [ "$n" -gt 0 ]; then echo $((n - 1)) > %[3]q; echo "Bootstrap failed: 5: Input/output error" >&2; exit 5; fi
	label=${3##*/}; : > %[2]q/"${label%%.plist}" ;;
esac
`, f.audit, f.loaded, f.failures)
	require.NoError(t, os.WriteFile(f.path, []byte(script), 0o755))
	return f
}

func (f *fakeLaunchctl) calls(t *testing.T) []string {
	t.Helper()
	data, err := os.ReadFile(f.audit)
	if os.IsNotExist(err) {
		return nil
	}
	require.NoError(t, err)
	return strings.Split(strings.TrimSpace(string(data)), "\n")
}

func TestClientLoadsChecksAndUnloadsInTheGUIDomain(t *testing.T) {
	f := newFakeLaunchctl(t)
	c := New(f.path, 501, 5*time.Second)
	ctx := context.Background()

	state, err := c.State(ctx, "com.example.job")
	require.NoError(t, err)
	assert.Equal(t, State{}, state)
	require.NoError(t, c.Load(ctx, "/home/Library/LaunchAgents/com.example.job.plist"))
	state, err = c.State(ctx, "com.example.job")
	require.NoError(t, err)
	assert.Equal(t, State{Loaded: true}, state)
	require.NoError(t, os.WriteFile(filepath.Join(f.loaded, "com.example.job"), []byte("running"), 0o600))
	state, err = c.State(ctx, "com.example.job")
	require.NoError(t, err)
	assert.Equal(t, State{Loaded: true, Running: true}, state, "the job's own state line, not its endpoints'")
	require.NoError(t, c.Unload(ctx, "com.example.job"))
	require.NoError(t, c.Unload(ctx, "com.example.job"), "a job that is already gone is unloaded")

	assert.Equal(t, []string{
		"print gui/501/com.example.job",
		"bootstrap gui/501 /home/Library/LaunchAgents/com.example.job.plist",
		"print gui/501/com.example.job",
		"print gui/501/com.example.job",
		"bootout gui/501/com.example.job",
		"bootout gui/501/com.example.job",
		"print gui/501/com.example.job",
	}, f.calls(t))
}

func TestClientRetriesABootstrapLaunchdIsNotReadyFor(t *testing.T) {
	f := newFakeLaunchctl(t)
	c := New(f.path, 501, 5*time.Second)
	c.retryWait = time.Millisecond

	require.NoError(t, os.WriteFile(f.failures, []byte("2"), 0o600))
	require.NoError(t, c.Load(context.Background(), "/p/com.example.job.plist"))
	assert.Len(t, f.calls(t), 3)

	require.NoError(t, os.WriteFile(f.failures, []byte("9"), 0o600))
	err := c.Load(context.Background(), "/p/com.example.other.plist")
	require.Error(t, err)
	assert.Contains(t, err.Error(), "Input/output error", "the error carries launchctl's reason")
	assert.Len(t, f.calls(t), 3+loadAttempts)
}

func TestClientReportsALaunchctlItCannotRun(t *testing.T) {
	c := New(filepath.Join(t.TempDir(), "missing"), 501, time.Second)
	_, err := c.State(context.Background(), "com.example.job")
	assert.Error(t, err)
}
