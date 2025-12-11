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
using System.Text;

namespace JetdriveSharp
{
	public delegate void ChannelValuePostedHandler(Object sender, ChannelValuePostedEventArgs e);

	public class JetdriveClient : JetdriveNode
	{
		/// <summary>
		/// Fixed provider name length. Must be padded with trailing 0's
		/// </summary>
		protected const int PROVIDER_NAME_LEN = 50;

		/// <summary>
		/// Fixed channel name length. Must be padded with trailing 0's
		/// </summary>
		protected const int CHANNEL_NAME_LEN = 30;


		/// <summary>
		/// Channels registered by incoming ChannelInfo messages
		/// Store by key=host, value = (key=chan_id, id_info)
		/// </summary>
		private readonly Dictionary<UInt16, Dictionary<UInt16, JDChannelInfo>> registeredChannels = new Dictionary<ushort, Dictionary<ushort, JDChannelInfo>>();

		/// <summary>
		/// Track all provider names against their host ids
		/// </summary>
		private readonly Dictionary<UInt16, String> providerNames = new Dictionary<ushort, string>();

		/// <summary>
		/// Fired whenever incoming channels are posted via a ChannelValues message
		/// </summary>
		public event ChannelValuePostedHandler ChannelPosted;

		/// <summary>
		/// Fired whenever a remote node calls clear channels on itself via a ClearChannels message.
		/// </summary>
		public event ClearChannelsHandler ChannelsCleared;

		public JetdriveClient(NetworkPort port, bool transmit, IHighAccuracyTimer timer) : base(port, transmit, timer)
		{
		}

		/// <summary>
		/// Request that the specified host transmit a ChannelInfo message
		/// </summary>
		/// <param name="dstHost"></param>
		public void RequestChannelInfo(UInt16 dstHost)
		{
			KLHDVMessage msg = new KLHDVMessage(MessageKey.RequestChannelInfo, this.HostId, dstHost, new byte[0]);
			Transmit(msg);
		}

		/// <summary>
		/// Removes a host's channel data (which fires the ChannelsCleared event), then calls JetdriveNode.EraseHost
		/// </summary>
		/// <param name="hostId"></param>
		public override void EraseHost(ushort hostId)
		{
			ClearChannelInfo(hostId);
			base.EraseHost(hostId);
		}


		protected override void OnMessageReceived(NetworkPort port, InboundKLHDVMessage msg)
		{
			//Ensure that our host ID has been established before processing messages, and filter out messages that this node may have transmitted.
			if (this.HostId == 0 || msg.Host != this.HostId)
			{
				switch (msg.Key)
				{
					case MessageKey.ChannelInfo: // Process an incoming ChannelInfo message
					{
						lock (registeredChannels)
						{
							Dictionary<UInt16, JDChannelInfo> ids;

							if (!registeredChannels.TryGetValue(msg.Host, out ids))
							{
								ids = new Dictionary<UInt16, JDChannelInfo>();
								registeredChannels.Add(msg.Host, ids);
							}

							//Parse out provider name...
							String providerName = Encoding.UTF8.GetString(msg.Value, 0, PROVIDER_NAME_LEN).TrimEnd('\0');

							//Use last provider name sent
							providerNames.Remove(msg.Host);
							providerNames.Add(msg.Host, providerName);

							//Parse each channel info object out...
							int idx = PROVIDER_NAME_LEN;
							while (idx + (sizeof(UInt16) + sizeof(byte) + CHANNEL_NAME_LEN + sizeof(byte)) <= msg.Length)
							{
								UInt16 channelId = BitConverter.ToUInt16(msg.Value, idx);
								idx += sizeof(UInt16);

								//Discard, we do nothing with this, but you can put some data in here if you wanna do some special stuff.
								byte vendorSpecifc = msg.Value[idx++];

								String channelName = Encoding.UTF8.GetString(msg.Value, idx, CHANNEL_NAME_LEN).Trim('\0');
								idx += CHANNEL_NAME_LEN;

								JDUnit unit = (JDUnit)msg.Value[idx++];

								JDChannelInfo info = new JDChannelInfo()
								{
									channelName = channelName,
									vendor_specific = vendorSpecifc,
									unit = unit
								};

								ids.Remove(channelId);
								ids.Add(channelId, info);
							}
						}

						break;
					}
					case MessageKey.ChannelValues: // Process incoming ChannelValues messages
					{
						if (ChannelPosted is ChannelValuePostedHandler handler)
						{
							ChannelValuePostedEventArgs args = null;

							//Parse in channel values and do stuff with them!
							int idx = 0;
							while (idx + 10 <= msg.Length)
							{
								UInt16 channelId = BitConverter.ToUInt16(msg.Value, idx);
								idx += sizeof(UInt16);

								UInt32 ts = BitConverter.ToUInt32(msg.Value, idx);
								idx += sizeof(UInt32);

								float val = BitConverter.ToSingle(msg.Value, idx);
								idx += sizeof(float);


								String providerName = null;
								JDChannelInfo info = null;
								lock (registeredChannels)
								{
									if (registeredChannels.TryGetValue(msg.Host, out Dictionary<UInt16, JDChannelInfo> ids))
									{
										ids.TryGetValue(channelId, out info);
									}

									providerNames.TryGetValue(msg.Host, out providerName);
								}

								//Calc TS

								DateTime? calcedTs = this.CalcTimestamp(msg.Host, ts);

								//Try and use the provider's TS sync, but if we haven't performed a time sync yet, just use local time, it's still fairly close.
								if (calcedTs != null)
								{
									//Note that info and provider name could be null if we haven't received any info yet, so probably ignore anything where info is null...
									args = new ChannelValuePostedEventArgs(info, providerName, calcedTs.Value, val, channelId, msg);
								}
								else
								{
									args = new ChannelValuePostedEventArgs(info, providerName, this.Timer.Now, val, channelId, msg);
								}

								handler(this, args);
							}

							
						}

						break;
					}
					case MessageKey.ClearChannelInfo: // Clear a host from the channel info cache
					{
						ClearChannelInfo(msg.Host);

						break;
					}
				}
			}
		}

		private void ClearChannelInfo(UInt16 hostId)
		{
			String hostname = null;
			lock (registeredChannels)
			{
				this.providerNames.TryGetValue(hostId, out hostname);
				registeredChannels.Remove(hostId);
				providerNames.Remove(hostId);
			}

			if (ChannelsCleared is ClearChannelsHandler handler)
			{
				handler(this, new ClearChannelsEventArgs(hostId, hostname));
			}
		}
	}
}
