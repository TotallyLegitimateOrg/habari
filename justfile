# Default recipe: list available commands
default:
    @just --list

# Run all tests
test *args:
    go test {{args}} -skip 'TestConversion' ./...

# Build the CLI binary
build out="./bin/habari":
    go build -o {{out}} ./cmd/habari

# Parse a filename
parse *args:
    go run ./cmd/habari "{{args}}"

# Build and install to $GOBIN
install:
    go install ./cmd/habari

# Run go vet
vet:
    go vet ./...

# Run tests with coverage
coverage:
    go test -cover -skip 'TestConversion' ./...
