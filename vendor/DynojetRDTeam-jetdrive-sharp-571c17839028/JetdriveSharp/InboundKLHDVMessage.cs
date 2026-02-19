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
	public sealed class InboundKLHDVMessage : KLHDVMessage
	{
		public InboundKLHDVMessage(MessageKey key, ushort host, ushort destination, byte[] value, SequenceNumberFlags flags) : base(key, host, destination, value)
		{
			this.Flags = flags;
		}

		private InboundKLHDVMessage()
		{
		}

		public SequenceNumberFlags Flags
		{
			get;internal set;
		}

		public static InboundKLHDVMessage Decode(byte[] data, int offset)
		{
			int idx = 0;

			InboundKLHDVMessage msg = new InboundKLHDVMessage();
			msg.Key = (MessageKey)data[offset + idx++];

			int length = BitConverter.ToUInt16(data, offset + idx);
			idx += sizeof(UInt16);

			if (offset + idx + length <= data.Length)
			{
				msg.Host = BitConverter.ToUInt16(data, offset + idx);
				idx += sizeof(UInt16);

				msg.SequenceNumber = data[offset + idx++];

				msg.Destination = BitConverter.ToUInt16(data, offset + idx);
				idx += sizeof(UInt16);

				//Now copy in data
				msg.Value = new byte[length];
				Buffer.BlockCopy(data, offset + idx, msg.Value, 0, length);
			}
			else
			{
				throw new IndexOutOfRangeException("Message length is greater than provided buffer length!");
			}

			return msg;
		}


	}
}
