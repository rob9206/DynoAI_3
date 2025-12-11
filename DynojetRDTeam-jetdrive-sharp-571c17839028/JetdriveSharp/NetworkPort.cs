/*
 
   Copyright 2020 Dynojet Research Inc

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.

 */
using System;
using System.Collections.Generic;
using System.Net;
using System.Net.Sockets;
using System.Text;

namespace JetdriveSharp
{
	public delegate void KLHDVMessageReceivedEventHandler(Object sender, KLHDVMessageReceivedArgs args);

	public class NetworkPort : IDisposable
	{
		private UdpClient client;

		private const ushort PORT = 22344; 
		private static readonly IPAddress mcastAddr = IPAddress.Parse("224.0.2.10"); // multicast address, subject to change, not set in stone yet.

		/// <summary>
		/// Fired whenever a KLHDV message is successfully received and decoded
		/// </summary>
		public event KLHDVMessageReceivedEventHandler MessageReceived;

		/// <summary>
		/// Join the multicast group to allow receipt of messages
		/// </summary>
		/// <param name="ifaceAddr"></param>
		public void Join(IPAddress ifaceAddr)
		{
			if (ifaceAddr is null)
			{
				throw new ArgumentNullException(nameof(ifaceAddr));
			}

			if (client != null)
			{
				throw new InvalidOperationException($"Cannot join the same client multiple times! Create a new {nameof(NetworkPort)} to rejoin.");
			}

			//Join mcast group
			client = new UdpClient();
			
			//This is critical to all implementations! If you don't set this socket option, other hosts on the same machine won't be able to join jetdrive. (Or your program won't be able to join if another app is already running)
			client.Client.SetSocketOption(SocketOptionLevel.Socket, SocketOptionName.ReuseAddress, true);

			//Try and bind do the endpoint...
			client.Client.Bind(new IPEndPoint(ifaceAddr, PORT));

			//Join a multicast group for a specific interface
			client.JoinMulticastGroup(mcastAddr, ifaceAddr);
		}

		/// <summary>
		/// Start asynchronously receiving messages. Note that messages received will be on worker threads, so don't assume a single thread for the OnMessage event.
		/// </summary>
		public void StartListening()
		{
			BeginReceive(client);
		}

		private void BeginReceive(UdpClient client)
		{
			client.BeginReceive(new AsyncCallback(UdpOnReceive), client);
		}

		private void UdpOnReceive(IAsyncResult ar)
		{
			if (ar != null)
			{
				try
				{
					UdpClient client = (UdpClient)ar.AsyncState;

					IPEndPoint endpoint = null;
					byte[] receiveBytes = client.EndReceive(ar, ref endpoint);

					//Try and decode KLHDV message.
					InboundKLHDVMessage msg = InboundKLHDVMessage.Decode(receiveBytes, 0);

					//Console.WriteLine($"Received message from 0x{msg.Host:X4} : {msg.Key}");

					if (MessageReceived is KLHDVMessageReceivedEventHandler handler)
					{
						handler(this, new KLHDVMessageReceivedArgs(msg));
					}

					BeginReceive(client);

				}
				catch (Exception x)
				{
					Console.WriteLine($"Network Port Error: {x}");
					//Handle network RX error...
				}
			}
			else
			{
				//This should never happen
			}
		}

		public void Transmit(KLHDVMessage msg)
		{
			//Convert KLHDV message to binary and transmit
			byte[] data = msg.Encode();
			client.Send(data, data.Length, new IPEndPoint(mcastAddr, PORT));
		}

		public void Dispose()
		{
			if (client != null)
			{
				client.DropMulticastGroup(mcastAddr);
				client.Dispose();
			}
		}
	}
}
