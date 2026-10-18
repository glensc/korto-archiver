"""GraphQL operations observed in Korto's web application."""

GET_MESSAGES_QUERY = """
query GetMessagesData($id: ID!, $archived: Boolean) {
  viewer {
    id
    apartment(id: $id) {
      id
      readings_allowed
      readings_end
      readings_missing
      association {
        id
        messages(archived: $archived) {
          id
          type
          datetime
          private
          unread
          pinned
          subject
          is_archived
          polls { id voting_open can_vote general_vote status __typename }
          __typename
        }
        __typename
      }
      __typename
    }
    __typename
  }
}
"""

GET_MESSAGE_QUERY = """
query GetMessageData($objectId: ID!, $type: MessageType!, $id: ID!) {
  viewer {
    id
    apartment(id: $objectId) {
      id
      association {
        id
        message(type: $type, id: $id) {
          id
          type
          from
          to
          official_id
          datetime
          edit_datetime
          edited_by
          unread
          private
          pinned
          is_announcement
          subject
          body
          status
          can_edit
          can_delete
          is_archived
          attachments { id filename download_url size __typename }
          replies {
            id
            from
            datetime
            edit_datetime
            edited_by
            body
            new_status
            new_to
            can_edit
            can_delete
            attachments { id filename download_url size __typename }
            __typename
          }
          polls {
            id
            type
            general_vote
            can_vote
            deadline
            voting_open
            resolution
            options { id text num_votes __typename }
            selected_options
            min_choices
            max_choices
            num_selected
            status
            motion_passed
            required_votes
            max_votes
            my_vote { voter options datetime proxy_vote comment __typename }
            apartment_votes { voter options datetime proxy_vote comment __typename }
            missing_votes
            summary_url
            quorum
            cast_votes
            abstained_votes
            invalid_votes
            voted_co_shares
            total_co_shares
            __typename
          }
          __typename
        }
        __typename
      }
      __typename
    }
    __typename
  }
}
"""
