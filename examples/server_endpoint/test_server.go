package main

import (
	"fmt"
	"log"
	"net/http"
	"time"
)

func healthHandler(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusOK)
	fmt.Fprintf(w, "OK")
}

func main() {
	// Add a 1-second delay before starting the server
	// This simulates a service that takes time to start up
	time.Sleep(1 * time.Second)

	http.HandleFunc("/health", healthHandler)

	fmt.Println("Starting HTTP server on port 8080...")
	log.Fatal(http.ListenAndServe(":8080", nil))
}
