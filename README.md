# DS Lab 6
This is my solution of the problem given on the DS Lab 6. It is simple implementation of file transferring with non-blocking sockets. <br>
## Running
There is no dependencies in the code which must be installed hence you can simply run the scripts.<br>
Server - [server.py](server.py) to start server-side script. It will use port 8800 and all possible ip addresses (0.0.0.0). You can change the settings in the file in constants section.<br>
Client - [client.py](client.py) to start client side script. It accepts 3 positional arguments: path to the local file, server hostname (or ip), server port. Usage example: ```python client.py file.ext example.com 8800```. The file will be sent to the server as soon as possible.<br>

## Other information
Note that if the file with some name exists on the server then new files with the same name will be renamed as follows: *file_name_copyN.extension* where N is the copy number.<br>
I used selector approach for the server-client communication.<br>
