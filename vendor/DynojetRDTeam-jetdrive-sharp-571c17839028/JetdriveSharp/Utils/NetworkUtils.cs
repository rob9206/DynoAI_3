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
using System.Net.NetworkInformation;
using System.Net.Sockets;
using System.Text;

namespace JetdriveSharp.Utils
{
	public static class NetworkUtils
	{
		/// <summary>
		/// This part is up to you! But we need to pick an IP address for the interface we want to communicate via (we don't really wanna join a multicast group on every IP on every interface, so just pick one).
		/// So far, I think we have two options for this:
		/// 1: Let the OS pick the best interface by checking which one is connected to the internet (the most likely correct IF for a LAN)
		/// 2: List all interfaces and IP addresses and allow the user to pick (We should ALLOW this, but it won't "just work" and users will have to pick an IF manually, which they probably don't know how to do).
		/// </summary>
		/// <returns></returns>
		public static bool TryGetBestLocalIFAddr(out IPAddress addr, String dnsIpAddr = "8.8.8.8")
		{
			addr = null;
			bool success = false;

			try
			{
				//Thanks to: https://stackoverflow.com/a/27376368/3908226
				using (Socket socket = new Socket(AddressFamily.InterNetwork, SocketType.Dgram, 0))
				{
					//Google DNS server IP address
					socket.Connect(dnsIpAddr, 65530);
					IPEndPoint endPoint = socket.LocalEndPoint as IPEndPoint;
					addr = endPoint.Address;
					success = true;
				}
			}
			catch (SocketException)
			{
				//Unable to connect, no internet!
			}

			return success;
		}


	}
}
