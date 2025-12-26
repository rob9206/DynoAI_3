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
using System.Text;
using System.Threading;

namespace JetdriveSharp
{
	public abstract class JetdriveNode : IDisposable
	{
		private struct OffsetInfo
		{
			public long offset;
			public UInt32 latency;
		}

		private volatile StallReason _StallStatus = StallReason.NotStalled;

		public const UInt16 ALL_HOSTS = 0xFFFF;

		public const byte JETDRIVE_VERSION = 0x01;
		protected const byte MAX_JETDRIVE_VERSION = 0x09;
		protected const byte MIN_JETDRIVE_VERSION = JETDRIVE_VERSION;


		protected const int CHANNEL_VALUES_SIZE = 0x0A;

		private int SequenceNumber;
		private NetworkPort Port
		{
			get; set;
		}

		/// <summary>
		/// Track sequence numbers for each remote host
		/// </summary>
		private readonly Dictionary<UInt16, byte> sequenceNumbers = new Dictionary<ushort, byte>();

		/// <summary>
		/// Timestamp offsets
		/// </summary>
		private readonly Dictionary<UInt16, OffsetInfo> offsets = new Dictionary<ushort, OffsetInfo>();

		private readonly bool transmit;

		protected IHighAccuracyTimer Timer
		{
			get; private set;
		}

		private volatile ushort _HostId;

		public ushort HostId
		{
			get
			{
				return _HostId;
			}
			private set
			{
				_HostId = value;
			}
		}

		/// <summary>
		/// Check to see if the node is stalled due to an error...
		/// </summary>
		public StallReason StallStatus
		{
			get
			{
				return _StallStatus;
			}
		}

		public event EventHandler Stalled;


		public JetdriveNode(NetworkPort port, bool transmit, IHighAccuracyTimer timer)
		{
			this.transmit = transmit;
			this.Port = port;
			port.MessageReceived += Port_MessageReceived;
			this.Timer = timer;
		}

		/// <summary>
		/// Remove a host's sequence number and time synchronization information. 
		/// </summary>
		/// <param name="hostId"></param>
		public virtual void EraseHost(UInt16 hostId)
		{
			lock (sequenceNumbers)
			{
				sequenceNumbers.Remove(hostId);
			}

			lock (offsets)
			{
				offsets.Remove(hostId);
			}
		}


		protected void Transmit(KLHDVMessage msg)
		{
			msg.SequenceNumber = GetNextSequenceNumber();
			Port.Transmit(msg);
		}


		protected byte GetNextSequenceNumber()
		{
			//Will always start as 1
			return (byte) (Interlocked.Increment(ref SequenceNumber) % 256);
		}

	
		public void NegotiateHostId()
		{
			this.HostId = 0;
			ClearStall();

			SendPing(ALL_HOSTS, null);

			Thread.Sleep(1000 * 1);

			Random random = new Random();
			UInt16 hostId = 0;
			lock (sequenceNumbers)
			{
				do
				{
					hostId = (UInt16)random.Next(0xFFFF);

				} while (hostId == 0x0 || sequenceNumbers.ContainsKey(hostId));
			}

			this.HostId = hostId;

			Console.WriteLine($"Negotiated host ID: 0x{this.HostId:X4}");

		}

		public void SendPing(UInt16 destination, byte[] userData)
		{
			int userDataLen = 0;
			if (userData != null)
			{
				userDataLen = userData.Length;
			}
			byte[] payload = new byte[1 + 4 + userDataLen];

			int i = 0;
			payload[i++] = JETDRIVE_VERSION;
			BitConverter.GetBytes(Timer.ElapsedMs).CopyTo(payload, i);
			i += sizeof(UInt32);

			if (userData != null)
			{
				Buffer.BlockCopy(userData, 0, payload, i, userData.Length);
			}

			KLHDVMessage msg = new KLHDVMessage(MessageKey.Ping, this.HostId, destination, payload);

			Transmit(msg);
		}


		private void SendPong(KLHDVMessage pingMsg)
		{
			int echoDataLen = pingMsg.Length - 5;

			byte[] payload = new byte[1 + sizeof(UInt32) + sizeof(UInt32) + echoDataLen];

			payload[0] = JETDRIVE_VERSION;

			//Copy source timestamp
			Buffer.BlockCopy(pingMsg.Value, 1, payload, 1, sizeof(UInt32));

			//Insert our timestamp
			BitConverter.GetBytes(Timer.ElapsedMs).CopyTo(payload, 5);

			//Copy echo data into payload buffer.
			Buffer.BlockCopy(pingMsg.Value, pingMsg.Length - 5, payload, 9, echoDataLen);

			KLHDVMessage pong = new KLHDVMessage(MessageKey.Pong, this.HostId, pingMsg.Host, payload);

			Transmit(pong);
		}

		private void HandlePong(KLHDVMessage pongMsg)
		{
			byte version = pongMsg.Value[0];

			if (version > MAX_JETDRIVE_VERSION || version < MIN_JETDRIVE_VERSION)
			{
				Stall(StallReason.InvalidVersionDetected);
			}
			else
			{
				lock (offsets)
				{
					UInt32 host_ts = BitConverter.ToUInt32(pongMsg.Value, 1);
					UInt32 remote_ts = BitConverter.ToUInt32(pongMsg.Value, 5);

					UInt32 currentTime = Timer.ElapsedMs;

					UInt32 latency = (currentTime - host_ts) / 2;

					long offset = (long)currentTime - (long)remote_ts;

					if (offsets.TryGetValue(pongMsg.Host, out OffsetInfo existingOffset))
					{
						//Best practices with Cristian's algorithm are to use the minimum detected latency as a latency value 
						offsets[pongMsg.Host] = new OffsetInfo() { offset = offset, latency = Math.Min(existingOffset.latency, latency) };
					}
					else
					{
						offsets.Add(pongMsg.Host, new OffsetInfo() { offset = offset, latency = latency });
					}
				}
			}
		}

		protected DateTime? CalcTimestamp(UInt16 host, UInt32 ts)
		{
			DateTime? retval = null;
			lock (offsets)
			{
				if (offsets.TryGetValue(host, out OffsetInfo info))
				{
					retval = Timer.BaseTime + TimeSpan.FromMilliseconds(ts + info.offset - info.latency);
				}
			}

			return retval;
		}


		private void Stall(StallReason reason)
		{
			if (reason != _StallStatus)
			{
				_StallStatus = reason;
				if (Stalled is EventHandler handler)
				{
					handler(this, EventArgs.Empty);
				}
			}
		}

		public void ClearStall()
		{
			_StallStatus = StallReason.NotStalled;
		}


		private void Port_MessageReceived(object sender, KLHDVMessageReceivedArgs args)
		{
			if (_StallStatus == StallReason.NotStalled)
			{
				//Detect address collision
				if (this.HostId != 0 && args.Message.Host == this.HostId && args.Message.Destination == this.HostId)
				{
					Stall(StallReason.AddressCollisionDetected);
				}
				else
				{
					SequenceNumberFlags flags = SequenceNumberFlags.None;
					lock (sequenceNumbers)
					{
						if (sequenceNumbers.TryGetValue(args.Message.Host, out byte seq))
						{
							byte expectedSeqNum = (byte)(seq + 1);

							if (args.Message.SequenceNumber == expectedSeqNum)
							{
								//OK
							}
							else if (args.Message.SequenceNumber > expectedSeqNum)
							{
								flags |= SequenceNumberFlags.PREVIOUS_MESSAGES_DROPPED;
							}
							else if (args.Message.SequenceNumber < expectedSeqNum)
							{
								flags |= SequenceNumberFlags.OUT_OF_ORDER;
							}

							sequenceNumbers[args.Message.Host] = args.Message.SequenceNumber;
						}
						else
						{
							sequenceNumbers.Add(args.Message.Host, args.Message.SequenceNumber);
							flags |= SequenceNumberFlags.FIRST_MESSAGE;
						}
					}

					args.Message.Flags = flags;


					//Handle pings here!
					if (args.Message.Destination == this.HostId || args.Message.Destination == ALL_HOSTS)
					{
						OnMessageReceived(sender as NetworkPort, args.Message);

						if (this.HostId != 0 && transmit && args.Message.Key == MessageKey.Ping)
						{
							//Send pong!
							SendPong(args.Message);

							//Check to see if we've ever encountered this host before, if we haven't, we need to send them a ping to try and determine latency for channels.
							bool sendPing = false;
							lock (offsets)
							{
								if (!offsets.ContainsKey(args.Message.Host))
								{
									//Send a ping to the host!
									sendPing = true;
								}
							}

							if (sendPing)
							{
								SendPing(args.Message.Host, null);
							}
						}

						//Handle pong messages
						if (args.Message.Key == MessageKey.Pong)
						{
							HandlePong(args.Message);
						}

					}
				}
			}
		}

		protected abstract void OnMessageReceived(NetworkPort port, InboundKLHDVMessage msg);

		public void Dispose()
		{
			Port.MessageReceived -= Port_MessageReceived;
		}
	}
}
