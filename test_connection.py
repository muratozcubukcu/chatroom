import socket
import sys
import time

def test_server_connection(host, port, attempts=3):
    print(f"\nTesting connection to {host}:{port}")
    print("-" * 50)

    for attempt in range(attempts):
        print(f"\nAttempt {attempt + 1} of {attempts}")
        try:
            # Create socket
            print("Creating socket...")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            
            # Start connection attempt
            start_time = time.time()
            print(f"Attempting to connect to {host}:{port}...")
            
            # Try to connect
            result = sock.connect_ex((host, port))
            
            # Calculate response time
            response_time = (time.time() - start_time) * 1000
            
            if result == 0:
                print(f"[SUCCESS] Connected in {response_time:.2f}ms")
                print("Testing basic communication...")
                
                # Try to send and receive data
                try:
                    sock.send(b'test')
                    print("[SUCCESS] Successfully sent test data")
                except Exception as e:
                    print(f"[FAILED] Failed to send data: {e}")
                
                sock.close()
                print("Connection test completed successfully!")
                return True
            else:
                print(f"[FAILED] Failed to connect (Error code: {result})")
                
        except socket.timeout:
            print("[FAILED] Connection timed out (server not responding)")
        except ConnectionRefusedError:
            print("[FAILED] Connection refused (server not accepting connections)")
        except socket.gaierror:
            print("[FAILED] Failed to resolve hostname")
        except Exception as e:
            print(f"[ERROR] Unexpected error: {str(e)}")
        finally:
            try:
                sock.close()
            except:
                pass
            
        # Wait before next attempt
        if attempt < attempts - 1:
            print("\nWaiting 2 seconds before next attempt...")
            time.sleep(2)
    
    print("\nAll connection attempts failed!")
    return False

def print_network_info():
    print("\nNetwork Information:")
    print("-" * 50)
    try:
        # Get local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        print(f"Local IP: {local_ip}")
    except:
        print("Could not determine local IP")
    
    try:
        # Get hostname
        hostname = socket.gethostname()
        print(f"Hostname: {hostname}")
    except:
        print("Could not determine hostname")

if __name__ == "__main__":
    # Get host and port from command line arguments or use defaults
    host = sys.argv[1] if len(sys.argv) > 1 else '98.237.241.248'
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
    
    print_network_info()
    
    # Run the test
    success = test_server_connection(host, port)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1) 